# Study 4 — Full Replication Procedure

## Overview

Study 4 is a longitudinal, live-tracking study that collects confidence interval predictions from three frontier LLMs daily, scores them against real-world outcomes as they resolve, and publishes results as a public index. This document contains every detail needed to replicate the study from scratch.

---

## 1. Research Question

Do frontier LLMs show systematic overconfidence in confidence intervals across domains and prediction horizons, and does this change over time?

---

## 2. Models

Each model is pinned to a specific version string. The exact string used for each prediction is recorded verbatim in the prediction file.

| Short name | Provider | Model ID | API package |
|-----------|----------|----------|-------------|
| claude | Anthropic | `claude-sonnet-4-6` | `anthropic` Python SDK |
| gpt4o | OpenAI | `gpt-4o-2024-11-20` | `openai` Python SDK |
| gemini | Google | `gemini-2.5-flash` | `google-genai` Python SDK |

If a model version is deprecated or updated mid-study, the change is logged in `config.yaml` under `model_version_changes` with the date, old ID, new ID, and a note. Both the old and new IDs are preserved in the prediction files.

---

## 3. Domains and Items

40 items total, fixed across the entire study. The same items are predicted every collection day.

### Stocks (10)

| Item ID | Label | Data source | Ticker |
|---------|-------|-------------|--------|
| SPY | S&P 500 ETF | Yahoo Finance | SPY |
| AAPL | Apple Inc. | Yahoo Finance | AAPL |
| MSFT | Microsoft Corp. | Yahoo Finance | MSFT |
| GOOGL | Alphabet Inc. | Yahoo Finance | GOOGL |
| NVDA | NVIDIA Corp. | Yahoo Finance | NVDA |
| AMZN | Amazon.com Inc. | Yahoo Finance | AMZN |
| META | Meta Platforms | Yahoo Finance | META |
| TSLA | Tesla Inc. | Yahoo Finance | TSLA |
| JPM | JPMorgan Chase | Yahoo Finance | JPM |
| BRK-B | Berkshire Hathaway B | Yahoo Finance | BRK-B |

### Crypto (10)

| Item ID | Label | Data source | CoinGecko ID |
|---------|-------|-------------|--------------|
| BTC | Bitcoin | CoinGecko | bitcoin |
| ETH | Ethereum | CoinGecko | ethereum |
| SOL | Solana | CoinGecko | solana |
| BNB | BNB | CoinGecko | binancecoin |
| XRP | XRP | CoinGecko | ripple |
| ADA | Cardano | CoinGecko | cardano |
| AVAX | Avalanche | CoinGecko | avalanche-2 |
| DOGE | Dogecoin | CoinGecko | dogecoin |
| DOT | Polkadot | CoinGecko | polkadot |
| LINK | Chainlink | CoinGecko | chainlink |

### Forex (10)

| Item ID | Label | Data source | yfinance ticker |
|---------|-------|-------------|-----------------|
| EUR/USD | Euro / US Dollar | Yahoo Finance | EURUSD=X |
| GBP/USD | British Pound / US Dollar | Yahoo Finance | GBPUSD=X |
| USD/JPY | US Dollar / Japanese Yen | Yahoo Finance | USDJPY=X |
| AUD/USD | Australian Dollar / US Dollar | Yahoo Finance | AUDUSD=X |
| USD/CAD | US Dollar / Canadian Dollar | Yahoo Finance | USDCAD=X |
| USD/CHF | US Dollar / Swiss Franc | Yahoo Finance | USDCHF=X |
| NZD/USD | New Zealand Dollar / US Dollar | Yahoo Finance | NZDUSD=X |
| USD/CNY | US Dollar / Chinese Yuan | Yahoo Finance | USDCNY=X |
| USD/MXN | US Dollar / Mexican Peso | Yahoo Finance | USDMXN=X |
| USD/SGD | US Dollar / Singapore Dollar | Yahoo Finance | USDSGD=X |

### Weather (10 cities)

Metric: daily mean temperature in degrees Fahrenheit.

| Item ID | Label | Latitude | Longitude | Data source |
|---------|-------|----------|-----------|-------------|
| New York | New York, USA | 40.7128 | -74.0060 | Open-Meteo |
| London | London, UK | 51.5074 | -0.1278 | Open-Meteo |
| Tokyo | Tokyo, Japan | 35.6762 | 139.6503 | Open-Meteo |
| Sydney | Sydney, Australia | -33.8688 | 151.2093 | Open-Meteo |
| Sao Paulo | Sao Paulo, Brazil | -23.5505 | -46.6333 | Open-Meteo |
| Lagos | Lagos, Nigeria | 6.5244 | 3.3792 | Open-Meteo |
| Mumbai | Mumbai, India | 19.0760 | 72.8777 | Open-Meteo |
| Toronto | Toronto, Canada | 43.6532 | -79.3832 | Open-Meteo |
| Dubai | Dubai, UAE | 25.2048 | 55.2708 | Open-Meteo |
| Berlin | Berlin, Germany | 52.5200 | 13.4050 | Open-Meteo |

---

## 4. Prediction Horizons

All three horizons are collected in a single API call per item per model.

| Horizon ID | Calendar days | Label |
|------------|---------------|-------|
| 1d | 1 | 1-Day |
| 1w | 7 | 1-Week |
| 1m | 30 | 1-Month |

Target date = prediction date + calendar days (not trading days).

---

## 5. Confidence Interval Levels

Three levels collected on every prediction call: **50%, 80%, 90%**.

Only the 90% level is displayed on the public website index. All three are stored and scored for research purposes, consistent with Studies 1-3.

---

## 6. Collection Schedule

- **When**: every weekday (Monday-Friday) at 16:30 UTC, after US market close
- **Weekend handling**: financial domains (stocks, crypto, forex) are skipped on weekends. Weather collection runs 7 days/week (configurable in `config.yaml`).
- **Automation**: GitHub Actions workflow `daily_collect.yml` triggers collection automatically. Can also be triggered manually via GitHub Actions UI.

---

## 7. Two-Call Design

Each item x model combination requires exactly **two separate API calls** per collection day. These must never be combined into a single call.

### Call 1: Prediction

The prediction call elicits structured JSON containing point estimates and confidence intervals for all three horizons. The model receives no chain-of-thought instruction and no request for reasoning. The response format is constrained to pure JSON.

### Call 2: Justification

The justification call is made **after** the prediction response has been received and parsed. The model's own prediction output is passed back to it, and it is asked to explain its reasoning. This ordering ensures the justification cannot influence the CI values.

There is a mandatory temporal separation: Call 2 cannot begin until Call 1's response is fully received.

---

## 8. Prompt Text (Verbatim)

All prompts are versioned. The current version is `PROMPT_VERSION = "1.0.0"`. Any change to prompt wording requires incrementing this version and logging it as a methodological event.

### Prediction prompt template

The `{context}` variable is populated differently per domain (see Section 9).

```
Today is {date}.

{context}

Provide point estimates and confidence intervals for {item_label} at three future horizons. Your intervals must be well-calibrated: a 90% CI should contain the true outcome approximately 90% of the time across many such predictions.

Horizons:
  1-day  target date: {date_1d}
  1-week target date: {date_1w}
  1-month target date: {date_1m}

Respond ONLY with valid JSON and no markdown fences:
{
  "1d": {
    "point_estimate": <number>,
    "50_ci": [<low>, <high>],
    "80_ci": [<low>, <high>],
    "90_ci": [<low>, <high>]
  },
  "1w": {
    "point_estimate": <number>,
    "50_ci": [<low>, <high>],
    "80_ci": [<low>, <high>],
    "90_ci": [<low>, <high>]
  },
  "1m": {
    "point_estimate": <number>,
    "50_ci": [<low>, <high>],
    "80_ci": [<low>, <high>],
    "90_ci": [<low>, <high>]
  }
}
```

### Justification prompt template

```
You previously made the following probabilistic forecast:

{prediction_json}

Please explain your reasoning in 2-4 paragraphs. Address:
1. What drove your point estimates at each horizon?
2. What sources of uncertainty influenced your confidence interval widths?
3. Are there specific risks or events that could push outcomes outside your stated intervals?

Write in plain English. No JSON, no bullet points.
```

---

## 9. Context Strings by Domain

The `{context}` variable in the prediction prompt is constructed as follows for each domain:

| Domain | Context template | Reference value source |
|--------|-----------------|----------------------|
| Stocks | `Current closing price of {label} ({id}): ${ref:.2f} USD as of {date}.` | `yfinance` `fast_info["lastPrice"]` |
| Crypto | `Current USD price of {label} ({id}): ${ref:.2f} as of {date}.` | CoinGecko `/simple/price` endpoint |
| Forex | `Current exchange rate for {id}: {ref:.4f} as of {date}.` | `yfinance` `fast_info["lastPrice"]` |
| Weather | `Yesterday's mean daily temperature in {label}: {ref:.1f} deg F (as of {yesterday}). Predict the mean daily temperature for the target dates below.` | Open-Meteo archive API, `temperature_2m_mean`, prior day |

### Why weather uses yesterday's mean (not current temperature)

The actuals for weather are daily mean temperatures from the Open-Meteo historical archive. To keep the reference value in the same units as the outcome variable, the reference value is yesterday's daily mean (also from the archive), not the real-time temperature at the moment of the API call.

---

## 10. Reference Value and Actuals Data Sources

### Stocks and Forex

- **Reference value (at collection time)**: `yfinance` Python library, `Ticker.fast_info["lastPrice"]`.
- **Actuals (at scoring time)**: `yfinance.download()` for the target date. Returns the closing price. If the target date is a weekend or holiday, the download window extends 7 days forward and takes the first available close. The adjusted date and any adjustment note are recorded.

### Crypto

- **Reference value**: CoinGecko free API, `GET /api/v3/simple/price?ids={coin_id}&vs_currencies=usd`.
- **Actuals**: CoinGecko historical API, `GET /api/v3/coins/{coin_id}/history?date={dd-mm-yyyy}`. Returns the USD price on that date. Crypto trades 24/7; no weekend adjustment needed.
- **Rate limiting**: 3-second pause between CoinGecko calls during collection; 3-second pause + 5-second exponential backoff on failure during actuals fetching.

### Weather

- **Reference value**: Open-Meteo archive API (`archive-api.open-meteo.com/v1/archive`), requesting `temperature_2m_mean` for the prior day in Fahrenheit.
- **Actuals**: Same Open-Meteo archive API for the target date.
- **Coordinates**: Fixed latitude/longitude per city (see Section 3).
- **No API key required**: Open-Meteo is free for non-commercial use.

---

## 11. Weekend and Holiday Handling

### Collection

- **Financial domains** (stocks, crypto, forex): skipped on Saturday and Sunday. Controlled by `config.yaml` field `weekend_collection.financial: false`.
- **Weather**: collected 7 days/week. Controlled by `config.yaml` field `weekend_collection.weather: true`.
- **Public holidays**: not handled explicitly. If the API returns no data for a target date, the fetcher extends the window forward up to 7 days and takes the first available value.

### Actuals resolution

- For stocks and forex: if the target date falls on a non-trading day, `yfinance.download()` is called with a 7-day window starting from the target date. The first available closing price is used. The actual resolution date and an adjustment note (e.g., "original 2026-04-05 was weekend; adjusted to 2026-04-07") are recorded in `actuals.csv`.
- For crypto: no adjustment needed (24/7 markets).
- For weather: no adjustment needed (daily mean always available).

---

## 12. Prediction File Schema

One JSON file per model per item per day. Filename pattern: `{model}_{domain}_{safe_item_id}_{date}.json`.

Examples:
- `claude_stocks_AAPL_2026-04-03.json`
- `gpt4o_crypto_BTC_2026-04-03.json`
- `gemini_forex_EURUSD_2026-04-03.json`
- `claude_weather_NewYork_2026-04-03.json`

### Fields

```json
{
  "model":              "claude",
  "model_id":           "claude-sonnet-4-6",
  "prompt_version":     "1.0.0",
  "pred_date":          "2026-04-03",
  "timestamp":          "2026-04-03T16:35:12Z",
  "domain":             "stocks",
  "item":               "AAPL",
  "item_label":         "Apple Inc.",
  "unit":               "USD",
  "current_value":      185.50,
  "context":            "Current closing price of Apple Inc. (AAPL): $185.50 USD as of 2026-04-03.",
  "prompt_text":        "<full verbatim prompt sent to model>",
  "raw_response":       "<full verbatim response from model>",
  "horizons": {
    "1d": {
      "point_estimate": 186.00,
      "50_ci": [184.00, 188.00],
      "80_ci": [182.00, 190.00],
      "90_ci": [181.00, 191.00]
    },
    "1w": { "..." : "..." },
    "1m": { "..." : "..." }
  },
  "justification_prompt": "<full verbatim justification prompt>",
  "justification_text":   "<full verbatim justification response>",
  "status":             "collected",
  "error":              null
}
```

If collection fails for any item, `status` is set to `"failed"` and `error` contains the error message. The file is still saved.

---

## 13. Actuals CSV Schema

File: `data/actuals/actuals.csv`. One row per (model, item, domain, prediction date, horizon).

| Column | Type | Description |
|--------|------|-------------|
| model | string | Short model name (claude, gpt4o, gemini) |
| domain | string | stocks, crypto, forex, weather |
| item | string | Item ID (e.g., AAPL, BTC, EUR/USD, New York) |
| pred_date | date | ISO 8601 date the prediction was made |
| horizon | string | 1d, 1w, or 1m |
| horizon_days | int | 1, 7, or 30 |
| target_date | date | pred_date + horizon_days |
| adjusted_target_date | date | Actual date the outcome was resolved (may differ from target_date for weekends/holidays) |
| unit | string | USD, rate, or deg F |
| current_value | float | Reference value at time of prediction |
| point_estimate | float | Model's point estimate for this horizon |
| ci_50_low | float | Lower bound of 50% CI |
| ci_50_high | float | Upper bound of 50% CI |
| ci_80_low | float | Lower bound of 80% CI |
| ci_80_high | float | Upper bound of 80% CI |
| ci_90_low | float | Lower bound of 90% CI |
| ci_90_high | float | Upper bound of 90% CI |
| actual_value | float | Resolved outcome (null if pending/failed) |
| adjustment_note | string | Explanation if target date was adjusted |
| status | string | resolved, failed, or pending |
| fetched_at | datetime | ISO 8601 timestamp when the actual was fetched |

---

## 14. Scoring

Scoring runs daily via `score.py`. It reads `actuals.csv`, filters to rows with `status == "resolved"`, and computes the following metrics.

### Hit rate

For each CI level L in {50, 80, 90}:

```
hit_L = 1  if  ci_L_low <= actual_value <= ci_L_high
         0  otherwise
```

### Brier score (normalized)

```
brier_score = ((point_estimate - actual_value) / current_value)^2
```

This is the same formula used in Studies 1-3. Division by `current_value` normalizes across items with different scales (e.g., BTC at $60,000 vs. DOGE at $0.15).

### ECE (Expected Calibration Error)

Computed per group (model x domain x horizon) over a set of predictions:

```
ECE = mean(|stated_level/100 - empirical_hit_rate|) across levels {50, 80, 90}
```

Where `empirical_hit_rate` for level L = `mean(hit_L)` across all predictions in the group.

### Scored CSV

File: `data/results/scored.csv`. Contains all columns from `actuals.csv` plus:

| Column | Type | Description |
|--------|------|-------------|
| hit_50 | float (0 or 1) | 1 if actual within 50% CI |
| hit_80 | float (0 or 1) | 1 if actual within 80% CI |
| hit_90 | float (0 or 1) | 1 if actual within 90% CI |
| brier_score | float | Normalized squared error |

### Summary CSV

File: `data/results/summary.csv`. Aggregated statistics per (model, domain, horizon) group:
- `hit_rate_50`, `hit_rate_80`, `hit_rate_90`
- `ece_50`, `ece_80`, `ece_90`, `mean_ece`
- `mean_brier`
- `n` (count of resolved predictions in group)

---

## 15. Rolling Index Computation

The public website index is a **rolling 30-day 90% CI hit rate** per model per horizon.

For each model M and horizon H on date D:

```
rolling_hit_rate_90(M, H, D) = mean(hit_90)
    for all predictions where:
        model == M
        horizon == H
        pred_date in [D - 30, D]
        status == "resolved"
```

The target value is 0.90. Values below 0.90 indicate overconfidence.

### Export files

`export_data.py` reads `scored.csv` and writes two JSON files to `website/data/`:

1. **`rolling_index.json`** -- current snapshot: per-model, per-horizon aggregate stats + per-domain breakdown.
2. **`time_series.json`** -- daily series of the rolling hit rate for each model/horizon, for the time-series chart.

---

## 16. Ramp-Up Period

Not all horizons produce data from Day 1.

| Day range | Available horizons |
|-----------|--------------------|
| Days 1-6 | 1-day only |
| Days 7-29 | 1-day + 1-week |
| Day 30+ | All three (steady state) |

The export script handles this by setting `status: "insufficient_data"` for horizons with no resolved predictions. The website displays a countdown (e.g., "1-week data available in 5 days") computed from `study.start_date` in config.yaml.

---

## 17. Graceful Degradation

The pipeline is designed to never abort a full run due to a single failure.

- If a model API call fails (after 3 retries with exponential backoff), the prediction file is saved with `status: "failed"` and `error` containing the message.
- If an actuals fetch fails, the row is written to `actuals.csv` with `status: "failed"` and the error in `adjustment_note`.
- Failed records are excluded from hit rate and ECE calculations.
- Each item/model combination is independent. A CoinGecko rate limit hitting BTC does not prevent AAPL from being collected.

---

## 18. Automation (GitHub Actions)

Three workflows run in sequence each weekday:

| Workflow | Cron (UTC) | Trigger | What it does |
|----------|------------|---------|--------------|
| `daily_collect.yml` | 16:30 Mon-Fri | Schedule + manual | Runs `collect_predictions.py`, commits prediction JSONs |
| `daily_score.yml` | 18:00 Mon-Fri | Schedule + manual | Runs `fetch_actuals.py` then `score.py`, commits results |
| `export.yml` | After Daily Score | `workflow_run` + manual | Runs `export_data.py`, commits website JSON |

All three workflows:
- Check out the repo with write permissions
- Set up Python 3.11 with pip caching
- Install `requirements.txt`
- Run the script(s)
- Commit any changed files and push (no-op if nothing changed)

API keys are stored as GitHub repository secrets and injected as environment variables.

---

## 19. Idempotency

- **Collection**: if a prediction file already exists for a given model/domain/item/date, the item is skipped. Re-running `collect_predictions.py` for the same date will only fill in missing items.
- **Actuals fetching**: rows already marked `status: "resolved"` in `actuals.csv` are skipped. Re-running `fetch_actuals.py` will only attempt unresolved rows.
- **Scoring**: `score.py` regenerates `scored.csv` from the full `actuals.csv` each run (not incremental). This is safe because scoring is a pure function of the input data.

---

## 20. File Naming and Storage

```
study4/
  data/
    predictions/   {model}_{domain}_{safe_id}_{date}.json
    actuals/       actuals.csv
    results/       scored.csv, summary.csv
  website/
    data/          rolling_index.json, time_series.json
```

Safe ID rules:
- Forex: slashes removed (EUR/USD -> EURUSD)
- Weather: spaces removed (New York -> NewYork)
- Stocks: hyphens replaced with underscores (BRK-B -> BRK_B)

---

## 21. Total Daily API Call Budget

```
40 items x 3 models x 2 calls (predict + justify) = 240 API calls/day
```

On weekends with weather-only collection:
```
10 items x 3 models x 2 calls = 60 API calls/day
```

---

## 22. Limitations

1. **Fixed item set**: the same 40 items are predicted every day. Models may develop implicit familiarity with the item list, though each API call is stateless (no conversation history).

2. **Single daily snapshot**: predictions are made once per day at a fixed time (16:30 UTC). Intraday volatility and time-of-day effects are not captured.

3. **No replication within day**: each prediction is made once per item per model per day (1 run, not 5 as in Studies 1-2). Stochasticity in model outputs is not averaged out.

4. **Free API rate limits**: CoinGecko's free tier imposes rate limits (~10-50 calls/minute). On rare occasions a crypto actual may not be retrieved. Affected predictions are marked as failed and excluded from scoring.

5. **Model version pinning is best-effort**: API providers may silently update model behavior behind a fixed version string. We log exact model IDs but cannot fully control for undisclosed upstream changes.

6. **Holiday handling**: public holidays are not explicitly coded. The system relies on data availability: if no market data exists for a target date, it takes the next available value. This may introduce small timing mismatches.

7. **Weather metric**: daily mean temperature is a single scalar that does not capture diurnal range, precipitation, or other weather variables.

8. **Prompt influence**: the prompt instructs models to be "well-calibrated." This framing may influence CI width differently across models. The prompt is fixed and versioned to ensure consistency within the study.

---

## 23. Replication Checklist

To replicate this study from scratch:

1. Clone the repository
2. Install Python 3.11+ and `pip install -r study4/requirements.txt`
3. Obtain API keys for Anthropic, OpenAI, and Google AI
4. Create a `.env` file in the project root with the three keys
5. Set `study.start_date` in `study4/config.yaml`
6. From the `study4/` directory, run:
   - `python collect_predictions.py` (daily)
   - `python fetch_actuals.py` (daily, after horizons elapse)
   - `python score.py` (after fetching actuals)
   - `python export_data.py` (after scoring)
7. For full automation, configure GitHub Actions with repository secrets
8. For the public website, deploy `study4/website/` to any static hosting provider

---

## 24. Relationship to Studies 1-3

| Dimension | Studies 1-3 | Study 4 |
|-----------|-------------|---------|
| Design | Cross-sectional snapshots | Longitudinal, continuous |
| Duration | Single day (Studies 1, 3) or backtest (Study 2) | Ongoing daily collection |
| Horizons | 1-day (Studies 1, 3), 1-22 trading days (Study 2) | 1-day, 1-week, 1-month |
| Domains | Equities only (Studies 1-2), 6 domains (Study 3) | 4 domains (stocks, crypto, forex, weather) |
| Runs per item | 5 (Studies 1-2), 1 (Study 3) | 1 |
| Public output | Paper (PDF) | Live website + paper data |
| Scoring formulas | Hit rate, ECE, Brier | Identical formulas |
| CI column naming | `ci_50_low` / `ci_50_high` (Study 3) | Same |
| Model calling | Single call per prediction | Two calls (prediction + justification) |

Study 4 was designed to address the "single-day snapshot" limitation explicitly noted in Studies 1 and 3.
