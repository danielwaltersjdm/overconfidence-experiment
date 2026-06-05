# Study 5 — MLB Game Outcome Calibration

Single-batch prediction study: each of three frontier LLMs (Claude, GPT-4o,
Gemini) gave confidence intervals for five quantities per game across 184
MLB regular-season games scheduled June 5–18, 2026. All predictions were
collected on 2026-06-04 (single batch). Actuals are fetched and scored
incrementally as games complete.

## Design

- **184 games × 3 models × 5 quantities = 2,760 individual CI predictions**
- All predictions made on **2026-06-04** for games on **2026-06-05 through 2026-06-18**
- Single 90% CI per quantity (no 50%/80% to keep prompts focused)
- Five quantities per game, chosen to test different kinds of knowledge:
  - `total_runs` — baseball-canonical, sportsbook-priced
  - `total_strikeouts` — pitching-specific
  - `total_home_runs` — discrete low-count, skewed
  - `duration_min` — non-skill (pace, replays, commercial breaks)
  - `attendance` — multi-factor (team popularity, day-of-week, venue)

## Models

| Display | Provider | Model ID |
|---|---|---|
| Claude | Anthropic | claude-sonnet-4-6 |
| GPT-4o | OpenAI | gpt-4o-2024-11-20 |
| Gemini | Google | gemini-2.5-flash |

## Pipeline

```
collect_predictions.py   # Run once on 2026-06-04 to predict all 184 games
fetch_actuals.py         # Run daily as games complete; idempotent
score.py                 # Joins predictions + actuals, computes calibration metrics
```

## Data sources

- **Schedule + boxscores + actuals**: MLB Stats API (`statsapi.mlb.com`, no auth)
- Every quantity verified available with 100% coverage on completed games
  (tested 2026-06-03 slate: 15/15 finished games returned all 5 quantities)

## Quantities and reliability

Verified extraction from completed games (2026-06-03 audit):
- `total_runs` — from boxscore `teams.{home,away}.teamStats.batting.runs`
- `total_strikeouts` — from `batting.strikeOuts` (sum across both teams)
- `total_home_runs` — from `batting.homeRuns` (sum)
- `duration_min` — from feed `gameData.gameInfo.gameDurationMinutes`
- `attendance` — from feed `gameData.gameInfo.attendance`

## Calibration metrics

Following Soll & Klayman (2004) and matching Studies 1–4:
- **Hit rate at 90%** — proportion of CIs containing the actual; target = 0.90
- **ECE** — |0.90 − hit_rate|
- **Accuracy (normalized MAD)** — mean(|actual − point| / |actual|)
- **μ (MEAD/MAD)** — implied σ from CI width, normalized to compare to actual deviations.
  < 1 = overconfident; = 1 = perfectly calibrated; > 1 = underconfident
