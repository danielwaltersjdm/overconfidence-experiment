# CLAUDE.md — Project Reference

## What This Project Is

A four-study empirical investigation of overconfidence in confidence interval estimates produced by frontier LLMs (Claude, GPT-4o, Gemini), scored against real-world ground-truth outcomes. Studies 1–3 are complete cross-sectional snapshots; Study 4 is a longitudinal live-tracking system with a public website.

---

## Folder Structure

```
overconfidence-experiment/
├── study1/               # 1-day equity predictions, 20 tickers, 5 runs/model
│   ├── predictions/      # 300 JSON files
│   └── results/          # scored.csv, summary.csv, charts
├── study2/               # Multi-horizon equity predictions, 100 tickers
│   ├── collect_predictions.py / fetch_actuals.py / score.py / visualize.py
│   ├── config.yaml
│   └── data/predictions/ + results/
├── study3/               # Multi-domain, single horizon
│   ├── domains/          # domain modules: stocks, crypto, forex, weather, commodities, nba
│   ├── collect_predictions.py / fetch_actuals.py / score.py / ...
│   ├── config.yaml
│   ├── data/predictions/ + results/
│   ├── build_ms.py       # fpdf2 generator → paper_ms.pdf (legacy, all 3 studies)
│   └── build_pdf.py      # fpdf2 generator → paper_pnas.pdf (legacy, Study 3 only)
├── paper/                # Canonical LaTeX paper
│   ├── main.tex          # PNAS format (current canonical)
│   ├── main_pre_PNAS_style.tex  # MS/INFORMS format backup
│   ├── pnas-new.cls / pnas-new.bst / pnasresearcharticle.sty
│   ├── references.bib    # All 13 cited works
│   ├── sections/
│   │   ├── introduction.tex
│   │   ├── study1.tex / study2.tex / study3.tex   # PNAS section split
│   │   ├── discussion.tex
│   │   └── *_pre_PNAS_style.tex  # MS-format backups (methods.tex, results.tex)
│   ├── overconfidence_pnas.pdf   # compiled output — PNAS format
│   ├── overconfidence_ms.pdf     # compiled output — MS/INFORMS format
│   ├── tables/           # (reserved)
│   └── figures/          # (reserved)
├── study4/               # Longitudinal live tracking (Study 4)
│   ├── collect_predictions.py / fetch_actuals.py / score.py / export_data.py
│   ├── config.yaml
│   ├── requirements.txt / README.md / .gitignore
│   ├── .github/workflows/   # daily_collect.yml, daily_score.yml, export.yml
│   ├── data/predictions/ + actuals/ + results/
│   └── website/             # static site: index.html, about.html, css/, js/, data/
├── paper/                # Canonical LaTeX paper
│   ├── main.tex          # PNAS format (current canonical)
│   ├── main_pre_PNAS_style.tex  # MS/INFORMS format backup
│   ├── pnas-new.cls / pnas-new.bst / pnasresearcharticle.sty
│   ├── references.bib    # All 13 cited works
│   ├── sections/
│   │   ├── introduction.tex
│   │   ├── study1.tex / study2.tex / study3.tex   # PNAS section split
│   │   ├── discussion.tex
│   │   └── *_pre_PNAS_style.tex  # MS-format backups (methods.tex, results.tex)
│   ├── overconfidence_pnas.pdf   # compiled output — PNAS format
│   ├── overconfidence_ms.pdf     # compiled output — MS/INFORMS format
│   ├── tables/           # (reserved)
│   └── figures/          # (reserved)
└── papers/               # Reference literature PDFs
```

---

## Studies

| Study | Design | N (per model) | Key variable |
|-------|--------|--------------|--------------|
| Study 1 | 20 equities, 1-day horizon, 5 runs/ticker | 100 | Baseline |
| Study 2 | 100 equities, 9 horizons (1–22d), 5 runs/ticker | 4,700–7,085 | Prediction horizon |
| Study 3 | 6 domains, 1-day horizon, 1 run/item | 68 resolved | Domain |
| Study 4 | 4 domains, 3 horizons (1d/1w/1m), daily collection, public index | ongoing | Longitudinal |

**Models (Studies 1–3)**: Claude (claude-sonnet-4-20250514), GPT-4 (gpt-4o), Gemini (gemini-2.5-flash)
**Models (Study 4)**: Claude (claude-sonnet-4-6), GPT-4o (gpt-4o-2024-11-20), Gemini (gemini-2.5-flash)
**Confidence levels**: 50%, 80%, 90%
**Prediction format**: Point estimate + three CIs as structured JSON

---

## Key Metrics

- **Hit rate** — proportion of predictions where true outcome fell within stated CI
- **ECE** — mean |stated coverage − empirical coverage| across 50/80/90% levels
- **Brier score** — normalized: `[(y_hat − y) / reference_price]²`
- **MEAD/MAD ratio (mu)** — Soll & Klayman (2004); mu < 1 = overconfidence, mu > 1 = underconfidence (Study 3 only)

---

## Key Findings

- GPT-4 is the most overconfident model in every study (ECE: 43.7%, 40.4%, 18.9%)
- Claude is best calibrated overall; Gemini is intermediate
- **Study 2**: Claude and GPT-4 degrade with horizon; Gemini holds calibration to 22 days
- **Study 3**: Domain-confidence inversion — all models overconfident in equities/commodities (mu < 1), underconfident in crypto/forex (mu > 1); uniform mu = 0.25 on commodities across all models

---

## Paper Output

| File | Format | Scope | Status |
|------|--------|-------|--------|
| `paper/main.tex` + section files | LaTeX / PNAS | All 3 studies | **Canonical editable source** |
| `paper/overconfidence_pnas.pdf` | Compiled PNAS | All 3 studies | Current output |
| `paper/overconfidence_ms.pdf` | Compiled MS/INFORMS | All 3 studies | Compiled from backup |
| `paper/main_pre_PNAS_style.tex` | LaTeX / MS/INFORMS | All 3 studies | Backup, not actively edited |

---

## LaTeX Paper Conventions (`paper/`)

- **Active format**: PNAS (`pnas-new.cls`, `pnasresearcharticle.sty`, `pnas-new.bst`)
- Compile from `paper/`: `pdflatex --disable-installer main && bibtex main && pdflatex --disable-installer main && pdflatex --disable-installer main`
- `pnas-new.cls` has `jabbrv` commented out (not in MiKTeX); `\JournalTitle` defined as passthrough in cls
- `pnasresearcharticle.sty` is a local file (not from MiKTeX) — sets `shortarticle=false`, `singlecolumn=false`
- Section files for PNAS: `introduction.tex`, `study1.tex`, `study2.tex`, `study3.tex`, `discussion.tex`
- `\acknow{}` + `\showacknow` used for acknowledgements (not `\begin{acknowledgments}`)
- Table 2 (Study 2 horizons) is **incomplete** — only 4 of 9 horizon rows present; full data in `study2/data/results/summary.csv`

---

## Study Script Conventions

- Study 2 scripts use **relative paths** — must be run from `study2/`
- Study 3 scripts use **relative paths** — must be run from `study3/`
- Study 4 scripts use **relative paths** — must be run from `study4/`
- fpdf2 builds use TTF fonts from `C:\Windows\Fonts`
- `ColManager` class manages two-column flow in both fpdf2 build scripts; do not enable fpdf2 auto page break
- Study 3/4 Google API: `from google import genai as google_genai` (newer `google-genai` package, not `google-generativeai`)
- Study 4 CI column names in CSV: `ci_50_low` / `ci_50_high` (consistent with Study 3)
- Study 4 prediction JSON: horizons keyed as `"1d"`, `"1w"`, `"1m"`; CI arrays as `"50_ci": [low, high]`
- Study 4 file naming: `{model}_{domain}_{safe_item_id}_{date}.json`

---

## Data Assumptions

- NBA (Study 3): 3 matchups permanently excluded — ESPN API never returned completed status
- Crypto (Study 3): n=20, not 25 — 5 outcomes unresolved due to CoinGecko rate limits
- Study 2: backtest mode (historical prices, date-blinded prompts); Studies 1 & 3: live mode
- Studies 1 & 3: single-day snapshots (stated limitation); Study 4 addresses this with longitudinal design
- Study 4: justification call is always a SEPARATE API call after prediction — do not merge
