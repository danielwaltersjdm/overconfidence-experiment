# Website Build Prompt — Study 4 LLM CI Index

Paste everything below into a new Claude Code session.

---

## Context

I have an empirical research project that tracks whether frontier AI models (Claude, GPT-4o, Gemini) are overconfident in their confidence interval predictions. Every weekday, all three models predict 40 items across stocks, crypto, forex, and weather at 1-day, 1-week, and 1-month horizons. We score their 90% confidence intervals against real outcomes and publish the results as a live public index.

The data pipeline is built and collecting data. I need a website to display the results.

## What exists already

The project lives at `C:\Users\dwalters1\overconfidence-experiment`. There is a skeleton website at `study4/website/` with placeholder files (index.html, about.html, css/styles.css, js/app.js). You should **replace these entirely** with a polished, production-ready site.

The website reads from two JSON files that are auto-generated daily by the pipeline and committed to `study4/website/data/`:

### `rolling_index.json` — current snapshot

```json
{
  "generated_at": "2026-04-06T18:00:00Z",
  "window_days": 30,
  "study_start_date": "2026-04-03",
  "data_through": "2026-04-06",
  "models": {
    "claude": {
      "model_id": "claude-sonnet-4-6",
      "horizons": {
        "1d": {
          "status": "active",         // or "insufficient_data"
          "days_until_first": 0,
          "n": 40,
          "hit_rate_50": 0.45,
          "hit_rate_80": 0.72,
          "hit_rate_90": 0.85,
          "ece_50": 0.05, "ece_80": 0.08, "ece_90": 0.05,
          "mean_ece": 0.06,
          "mean_brier": 0.0014,
          "domains": {
            "stocks":  { "n": 10, "hit_rate_90": 0.80, ... },
            "crypto":  { "n": 10, "hit_rate_90": 0.90, ... },
            "forex":   { "n": 10, "hit_rate_90": 0.85, ... },
            "weather": { "n": 10, "hit_rate_90": 0.88, ... }
          }
        },
        "1w": { "status": "insufficient_data", "days_until_first": 4 },
        "1m": { "status": "insufficient_data", "days_until_first": 27 }
      }
    },
    "gpt4o": { ... },
    "gemini": { ... }
  }
}
```

### `time_series.json` — daily series for charts

```json
{
  "generated_at": "2026-04-06T18:00:00Z",
  "window_days": 30,
  "horizons": {
    "1d": {
      "status": "active",
      "dates": ["2026-04-04", "2026-04-05", ...],
      "models": {
        "claude": { "hit_rate_90": [0.85, 0.87, ...], "n": [40, 80, ...] },
        "gpt4o":  { "hit_rate_90": [0.62, 0.60, ...], "n": [40, 80, ...] },
        "gemini": { "hit_rate_90": [0.75, 0.73, ...], "n": [40, 80, ...] }
      }
    },
    "1w": { "status": "insufficient_data" },
    "1m": { "status": "insufficient_data" }
  }
}
```

## Design requirements

**Audience**: General public, not researchers. Plain language throughout. Think Bloomberg terminal meets a clean dashboard.

**Tech stack**:
- Static site only. No backend, no build step, no framework.
- HTML + CSS + vanilla JS
- Chart.js for charts (load from CDN)
- Must work by opening index.html directly or via static host (Vercel/Netlify)

**Landing page (index.html) must show:**

1. **Headline**: "Do AI Models Know What They Don't Know?" or similar
2. **Three model cards** showing the current rolling 30-day 90% CI hit rate for each model (Claude, GPT-4o, Gemini). Color-coded: green if >= 0.85, amber if 0.70-0.85, red if < 0.70. Show "Building data" if insufficient.
3. **Horizon tabs**: 1-Day / 1-Week / 1-Month toggle. Disabled with tooltip if insufficient data.
4. **Time-series line chart**: rolling 30-day 90% CI hit rate over time for all 3 models on one chart. Horizontal red dashed line at 0.90 (target). Model colors: Claude = purple (#7c3aed), GPT-4o = green (#059669), Gemini = amber (#d97706).
5. **Domain breakdown table**: per-domain 90% CI hit rate for each model, for the selected horizon.
6. **Plain-English explainer section**: What a 90% CI means, what overconfidence is, what the target line represents.
7. **Data status bar**: shows when data was last updated, with a green/amber/red dot.

**Ramp-up handling**: During the first 30 days, some horizons won't have data yet. Show a friendly message like "1-week predictions resolve starting April 10th — check back then" instead of empty charts. Calculate from `study_start_date` in the JSON.

**About page (about.html) must include:**
- Study design: 3 models, 4 domains, 40 items, 3 horizons, 3 CI levels
- What models are used (with exact version IDs)
- All 40 items listed by domain
- Definition of the index metric (rolling 30-day 90% CI hit rate)
- How predictions are collected (including the two-call design: prediction then justification)
- Scoring formulas: hit rate, ECE, Brier score
- Limitations (fixed item set, single daily snapshot, model version pinning, rate limits)
- Link to GitHub repo: github.com/danielwaltersjdm/overconfidence-experiment

**Design principles:**
- Mobile responsive
- Fast load time (data files < 1MB each)
- Clean, modern look. Dark header, light body. System fonts.
- No unnecessary animation or decoration
- Professional enough for an academic project but accessible to non-researchers

**Model display names:**
- claude → "Claude"
- gpt4o → "GPT-4o"  
- gemini → "Gemini"

## File structure

Write these files:
```
study4/website/
├── index.html
├── about.html
├── css/
│   └── styles.css
├── js/
│   └── app.js
└── data/          # (already exists, populated by pipeline)
    ├── rolling_index.json
    └── time_series.json
```

## Important

- Read the existing files first before overwriting them
- The `data/` directory already has .gitkeep — don't remove it
- Include sample/mock data inline in a `<script>` tag or separate mock file so the site looks good even before real data is available. The mock data should show realistic values (Claude at ~85% hit rate, GPT-4o at ~60%, Gemini at ~75%).
- Test that the site degrades gracefully if the JSON files don't exist or are empty
- Do not add any build tools, package.json, or npm dependencies
