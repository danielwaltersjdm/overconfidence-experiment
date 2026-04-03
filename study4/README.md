# Study 4 — Longitudinal LLM Confidence Interval Tracking

A fully automated pipeline that collects daily confidence interval predictions from three
frontier LLMs, scores them against real-world outcomes, and publishes results as a live
public index.

---

## Quick-start

```bash
cd study4
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python collect_predictions.py --dry-run   # smoke test, no API calls
```

---

## Setup

### 1. API keys

The pipeline needs three API keys. **Never commit keys to the repository.**

For local development, create `study4/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
```

For GitHub Actions, add the same three keys as **repository secrets**:

1. Go to **Settings → Secrets and variables → Actions → New repository secret**
2. Add each of:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `GOOGLE_API_KEY`

The workflow YAML files reference these secrets as `${{ secrets.ANTHROPIC_API_KEY }}` etc.

### 2. Study start date

Edit `config.yaml` and set `study.start_date` to the ISO date when collection begins
(e.g. `"2026-04-07"`). This date is used to compute ramp-up state on the website.

### 3. Deploy the website

The static site lives in `study4/website/`. No build step is required.

**Vercel:**
1. Import the repository in Vercel
2. Set the **Root Directory** to `study4/website`
3. Framework preset: **Other** (plain static)
4. Deploy

**Netlify:**
1. New site from Git → select repository
2. Build command: *(leave empty)*
3. Publish directory: `study4/website`
4. Deploy

The site will auto-redeploy whenever `study4/website/data/` is updated by the
`export.yml` GitHub Actions workflow.

---

## Pipeline overview

```
Daily at 16:30 UTC            Daily at 18:00 UTC          After scoring
─────────────────────         ─────────────────────        ──────────────
collect_predictions.py   →    fetch_actuals.py        →   export_data.py
                              score.py
```

| Script | Input | Output |
|--------|-------|--------|
| `collect_predictions.py` | config.yaml, API keys | `data/predictions/*.json` |
| `fetch_actuals.py` | prediction JSONs | `data/actuals/actuals.csv` |
| `score.py` | actuals.csv | `data/results/scored.csv`, `summary.csv` |
| `export_data.py` | scored.csv | `website/data/rolling_index.json`, `time_series.json` |

### Running manually

```bash
# From study4/ directory
python collect_predictions.py                  # today's predictions
python collect_predictions.py --date 2026-04-07  # specific date
python collect_predictions.py --dry-run        # mock responses, no API calls
python collect_predictions.py --domain stocks --model claude  # subset

python fetch_actuals.py
python score.py
python export_data.py
```

---

## Failure alerting (GitHub Actions)

GitHub will send email on workflow failure if you have notifications enabled:

1. Go to **github.com → Profile → Settings → Notifications**
2. Under **Actions**, enable **Email** for "Failed workflows only"

For team alerts (Slack, PagerDuty, etc.), add a step to the workflow YAML:
```yaml
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    slack-message: "Study 4 pipeline failed: ${{ github.workflow }}"
  env:
    SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

---

## Directory structure

```
study4/
├── config.yaml                  # domain/item/model configuration
├── collect_predictions.py       # prediction + justification collection
├── fetch_actuals.py             # fetch resolved outcomes
├── score.py                     # hit rate, ECE, Brier score
├── export_data.py               # generate website JSON
├── requirements.txt
├── .github/workflows/
│   ├── daily_collect.yml        # 16:30 UTC Mon–Fri
│   ├── daily_score.yml          # 18:00 UTC Mon–Fri
│   └── export.yml               # triggers after daily_score
├── data/
│   ├── predictions/             # {model}_{domain}_{item}_{date}.json
│   ├── actuals/                 # actuals.csv
│   └── results/                 # scored.csv, summary.csv
├── website/
│   ├── index.html
│   ├── about.html
│   ├── css/styles.css
│   ├── js/app.js
│   └── data/                    # rolling_index.json, time_series.json
│                                # (written by export_data.py)
└── logs/                        # pipeline run logs (gitignored)
```

---

## Methodology notes

### Two-call design (prediction + justification)

Each item gets two separate API calls:
1. **Prediction call** — returns structured JSON with point estimates and CIs
2. **Justification call** — passes the prediction back to the model and asks for free-text reasoning

These are **never merged into a single call**. The prediction response must be received
before the justification call is made. This prevents the reasoning from influencing the CI values.

### Prompt versioning

`PROMPT_VERSION` in `collect_predictions.py` is a constant that must be incremented
whenever the prompt wording changes. Any prompt change is a methodological event.
Record it in `config.yaml` under `model_version_changes`.

### Model version pinning

The model ID strings in `config.yaml` are pinned to specific versions. If a provider
updates the model mid-study, log the change in `config.yaml → model_version_changes`
and update the version string. The exact model ID is stored verbatim in every
prediction file.

---

## How to add a new domain or item

1. Add the item to the appropriate section in `config.yaml`
2. Ensure the `actuals_source` is supported in `fetch_actuals.py`
3. No code changes needed if the domain type already exists
4. New domains require a new fetcher function in `fetch_actuals.py`

## How to handle a model deprecation

1. Update `model_id` in `config.yaml` to the replacement model ID
2. Add an entry to `model_version_changes` with the date and both IDs
3. The prediction file for the transition date will contain the new ID;
   all prior files retain the old ID — this is intentional and correct
4. Update `about.html` to reflect the new model version

---

## Scoring formulas (consistent with Studies 1–3)

**Hit rate** — `mean(1 if ci_low ≤ actual ≤ ci_high else 0)` per CI level

**ECE** — `mean(|stated_level/100 − empirical_hit_rate|)` across 50%, 80%, 90%

**Brier score** — `((point_estimate − actual) / current_value)²`

These are identical to the formulas used in Studies 1–3 of this project.
