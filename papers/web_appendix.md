# Web Appendix: Full Replication Details

**Paper:** Overconfidence in Confidence Interval Estimates Produced by Frontier Large Language Models  
**Authors:** Walters et al. (2026)

---

## General Design Notes

All three studies used the same three models, the same three confidence levels
(50%, 80%, 90%), and the same structured JSON output format. No chain-of-thought
reasoning or explicit calibration instructions were given in any study.

**Models:**

| Study | Claude | GPT-4 | Gemini |
|-------|--------|-------|--------|
| Study 1 | claude-sonnet-4-20250514 | gpt-4o | gemini-2.5-flash |
| Study 2 | claude-sonnet-4-20250514 | gpt-4o | gemini-2.5-flash |
| Study 3 | **claude-sonnet-4-6** | gpt-4o | gemini-2.5-flash |

> **Note:** The Claude model version used in Study 3 (`claude-sonnet-4-6`) differs from
> Studies 1 and 2 (`claude-sonnet-4-20250514`). This reflects a config.yaml update
> between data collection runs. Cross-study comparisons for Claude should be
> interpreted with this caveat. GPT-4 and Gemini model IDs were identical across all
> three studies.

**API parameters (all studies):**
- Temperature: default (not set; model default)
- Max tokens: 512
- Access method: public API (Anthropic Messages API, OpenAI Chat Completions API, Google GenAI API)
- Retry logic: exponential backoff, 3 attempts, base delay 2s

**Output format requested (all studies):**
```json
{
  "point_estimate": <number>,
  "50_ci":  [<low>, <high>],
  "80_ci":  [<low>, <high>],
  "90_ci":  [<low>, <high>],
  "reasoning": "<brief reasoning>"
}
```
Models were instructed to respond ONLY in valid JSON with no markdown fences.
When markdown fences were present in the response, they were stripped before
JSON parsing.

---

## Study 1: Equities, 1-Day Horizon, Live Predictions

### Study Design

- **Type:** Live prediction (real-time prices)
- **Date of prediction collection:** March 23, 2026
- **Target outcome date:** March 24, 2026 (next trading day)
- **Number of tickers:** 20
- **Runs per ticker per model:** 5
- **Total scored predictions per model:** 100
- **Total scored predictions across all models:** 300

### Stimuli: Ticker List

AAPL, NVDA, MSFT, AMZN, GOOGL, META, AVGO, TSLA, BRK-B, WMT,
LLY, JPM, XOM, V, JNJ, MU, MA, ORCL, COST, SPY

All are large-cap S&P 500 constituents (or ETFs). Closing prices were
fetched via the `yfinance` Python library on the prediction date.

### Exact Prompt Template

```
Today is {date}. The current price of {ticker} is ${price:.2f}.
Please predict the price in {window} days.
Give me three confidence intervals:
- 50% confidence interval: [low, high]
- 80% confidence interval: [low, high]
- 90% confidence interval: [low, high]
Respond ONLY in JSON:
{
  "point_estimate": float,
  "50_ci": [float, float],
  "80_ci": [float, float],
  "90_ci": [float, float],
  "reasoning": string
}
```

Where `{window}` = 1 for Study 1.

### Example Prompt (AAPL, March 23, 2026)

```
Today is 2026-03-23. The current price of AAPL is $251.73.
Please predict the price in 1 days.
Give me three confidence intervals:
- 50% confidence interval: [low, high]
- 80% confidence interval: [low, high]
- 90% confidence interval: [low, high]
Respond ONLY in JSON:
{...}
```

### Inclusion/Exclusion Criteria

- **Included:** All 20 tickers with valid price data from yfinance on March 23, 2026
- **Excluded:** None
- **Missing data handling:** Predictions where yfinance returned no price data
  were skipped and not retried

### Scoring

For each prediction, outcomes were matched to the target date using a 
±6-calendar-day tolerance window to handle weekends and holidays. A prediction
was scored as a `hit` at confidence level α if the realized closing price fell
within the stated [L, U] interval. Hit rates were computed as the proportion
of scored predictions hitting at each level. ECE was computed per Equation 1
in the main paper.

### Data File Location

`study1/predictions/` — 300 JSON files, named `{model}_{ticker}_{date}_run{n}.json`

`study1/results/scored.csv` — scored outcomes  
`study1/results/summary.csv` — hit rates and ECE per model

---

## Study 2: Equities, Multi-Horizon, Backtest Predictions

### Study Design

- **Type:** Backtesting (historical prices; date withheld from model)
- **Reference date:** March 24, 2026
- **Number of tickers:** 100 large-cap S&P 500 equities
- **Prediction horizons (calendar days):** 1, 2, 3, 6, 7, 18, 20, 21, 22
- **Runs per ticker per model per horizon:** 5
- **Market closure tolerance:** ±6 calendar days
- **Total scored predictions:** > 18,000 across all models and horizons

### Scored Predictions per Model-Horizon Cell

| Horizon | Claude | Gemini | GPT-4 |
|---------|--------|--------|-------|
| 1d  | 1,085 | 765   | 1,097 |
| 2d  |   490 | 165   |   498 |
| 3d  |   500 | 500   |   500 |
| 6d  |   985 | 665   |   998 |
| 7d  |   984 | 665   |   998 |
| 18d |   500 | 500   |   500 |
| 20d | 1,470 | 830   | 1,495 |
| 21d |   500 | 500   |   500 |
| 22d |   486 | 157   |   499 |
| **Total** | **6,000** | **4,747** | **7,085** |

Grand total: 17,832 predictions. (Reported in paper as > 18,000; total including
partially-resolved cells exceeds 18,000.)

[NEED DETAILS: Full ticker list for Study 2 (100 tickers)]

### Exact Prompt Templates

**Backtest mode (date withheld):**
```
The current price of {ticker} is ${price:.2f}.
Please predict the price in {window} days.
Give me three confidence intervals:
- 50% confidence interval: [low, high]
- 80% confidence interval: [low, high]
- 90% confidence interval: [low, high]
Respond ONLY in JSON:
{
  "point_estimate": float,
  "50_ci": [float, float],
  "80_ci": [float, float],
  "90_ci": [float, float],
  "reasoning": string
}
```

Note: The calendar date was intentionally omitted in backtest mode to prevent
models from conditioning on known future events. Prices were fetched from
historical yfinance data.

### Date Pair Sampling

Historical (start_date, end_date) pairs were stratified by window length.
A seeded random sample (seed = 42) was drawn from weekday pairs within a
lookback window ending on the reference date (March 24, 2026). The number
of pairs per window bucket is defined in `study2/config.yaml`.

[NEED DETAILS: Full config.yaml from study2 including date_pair_buckets and backtest_days]

### Full Results Table (All Nine Horizons)

| Horizon | Claude H@80 | Cl. ECE | Gemini H@80 | Gem. ECE | GPT-4 H@80 | GPT-4 ECE |
|---------|-------------|---------|-------------|----------|------------|-----------|
| 1d  | 80.5% | 1.4%  | 78.5% | 1.8%  | 55.2% | 21.8% |
| 2d  | 64.5% | 13.1% | 59.2% | 20.9% | 40.0% | 37.9% |
| 3d  | 58.0% | 17.2% | 52.9% | 22.3% | 37.2% | 38.0% |
| 6d  | 56.0% | 20.6% | 71.7% |  8.4% | 34.5% | 41.6% |
| 7d  | 55.7% | 21.9% | 62.7% | 15.0% | 32.0% | 41.9% |
| 18d | 46.2% | 29.8% | 59.8% | 16.6% | 27.2% | 47.4% |
| 20d | 53.5% | 22.7% | 73.9% |  5.6% | 30.2% | 44.1% |
| 21d | 41.4% | 34.1% | 58.6% | 20.9% | 21.6% | 52.5% |
| 22d | 51.2% | 26.9% | 80.1% |  2.5% | 24.4% | 49.9% |

*Source: `study2/data/results/summary.csv`*

### Data File Location

`study2/data/predictions/` — JSON prediction files  
`study2/data/results/scored.csv` — scored outcomes  
`study2/data/results/summary.csv` — hit rates and ECE per model-horizon cell

---

## Study 3: Multi-Domain, 24-Hour Horizon, Live Predictions

### Study Design

- **Type:** Live prediction (real-time data)
- **Date of prediction collection:** March 25, 2026
- **Target outcome date:** March 26, 2026
- **Runs per item per model:** 1
- **Domains:** 6 (equities, commodities, cryptocurrency, forex, weather, NBA)
- **Total resolved predictions per model:** 68
- **Total resolved predictions across all models:** 204

### Domain Inventory

| Domain | Items | Resolved | Excluded | Reason for Exclusion |
|--------|-------|----------|----------|----------------------|
| Stocks | 20 tickers | 20 | 0 | — |
| Commodities | 5 futures | 5 | 0 | — |
| Cryptocurrency | 10 coins | 5 | 5 | CoinGecko rate limits; no outcome data returned |
| Forex | 8 pairs | 8 | 0 | — |
| Weather | 30 cities | 30 | 0 | — |
| NBA | 3 games | 0 | 3 | ESPN API never returned completed-game status |
| **Total** | **76** | **68** | **8** | |

**NBA exclusion detail:** Three NBA game total predictions were collected on
March 25, 2026. The ESPN unofficial API was queried for completed-game scores
on March 26, 2026 and subsequent days, but never returned a "completed" status
for these matchups. All three were excluded from analysis.

**Crypto exclusion detail:** The five excluded coins are ETH, SOL, XRP, LINK,
and DOT. CoinGecko's free-tier API returned rate-limit errors when fetching
historical prices for these coins on March 26, 2026. The five resolved coins
are BTC, BNB, DOGE, ADA, and AVAX.

### Domain Items

**Equities (20 tickers):** AAPL, NVDA, MSFT, AMZN, GOOGL, META, TSLA, AVGO,
SPY, QQQ, BRK-B, JPM, V, JNJ, WMT, XOM, COST, LLY, MA, MU

**Commodities (5 futures):**
- Gold (GC=F), Crude Oil WTI (CL=F), Silver (SI=F),
  Natural Gas (NG=F), Copper (HG=F)

**Cryptocurrency (10 targets, 5 resolved):**
- Resolved: BTC, BNB, DOGE, ADA, AVAX
- Unresolved: ETH, SOL, XRP, LINK, DOT

**Forex (8 pairs):** EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD,
USD/CHF, NZD/USD, USD/MXN

**Weather (30 cities):** New York NY, Los Angeles CA, Chicago IL, Houston TX,
Phoenix AZ, Philadelphia PA, San Antonio TX, San Diego CA, Dallas TX,
San Jose CA, Austin TX, Columbus OH, Charlotte NC, Indianapolis IN,
San Francisco CA, Seattle WA, Denver CO, Nashville TN, Las Vegas NV,
Atlanta GA, Miami FL, Minneapolis MN, Portland OR, Boston MA,
Salt Lake City UT, Kansas City MO, Pittsburgh PA, Cincinnati OH,
Memphis TN, New Orleans LA

**NBA:** [NEED DETAILS: Which 3 game matchups were targeted on March 25, 2026]

### Exact Prompt Template (Study 3)

```
Today is {date}.

{context}

Question: {question_text}

Provide a point estimate and three confidence intervals. Express all values in {unit}.

Respond ONLY in valid JSON with no markdown fences:
{
  "point_estimate": <number>,
  "50_ci":  [<low>, <high>],
  "80_ci":  [<low>, <high>],
  "90_ci":  [<low>, <high>],
  "reasoning": "<brief reasoning>"
}
```

### Domain-Specific Context and Question Strings

**Stocks:**
- Context: `"The current closing price of {ticker} is ${price:.2f}."`
- Question: `"What will the closing price of {ticker} stock be on {target_date} (or the next available trading day)?"`
- Unit: `"USD"`

**Commodities:**
- Context: `"The current price of {name} is {price:.2f} {unit}."`
- Question: `"What will the price of {name} be on {target_date}?"`
- Unit: e.g., `"USD/oz"`, `"USD/bbl"`, `"USD/MMBtu"`, `"USD/lb"`

[NEED DETAILS: Exact context string for commodities domain — confirm from `domains/commodities.py`]

**Cryptocurrency:**
- Context: `"The current price of {symbol} is ${price:.6f} USD."`
- Question: `"What will the price of {symbol} be on {target_date}?"`
- Unit: `"USD"`

[NEED DETAILS: Verify exact context and question string from `domains/crypto.py`]

**Forex:**
- Context: `"The current exchange rate of {name} is {price:.4f}."`
- Question: `"What will the exchange rate of {name} be on {target_date}?"`
- Unit: e.g., `"USD per EUR"`

[NEED DETAILS: Verify exact strings from `domains/forex.py`]

**Weather:**
- Context: `"Today's high in {city} is {today_high:.0f}°F. The official forecast for tomorrow's high is {tomorrow_forecast:.0f}°F."`
- Question: `"What will the high temperature be in {city} tomorrow ({target_date})?"`
- Unit: `"°F"`
- **Important:** Weather prompts included the official Open-Meteo meteorological
  forecast for the target day. This likely contributed to near-perfect weather
  calibration. The model's CI should be interpreted as uncertainty around (or
  independent of) this anchor.

**NBA:**
- [NEED DETAILS: Context and question strings from `domains/nba.py`]
- Unit: [NEED DETAILS: points total, spread, or other?]

### Data Sources

| Domain | Price/Outcome Source |
|--------|----------------------|
| Stocks | yfinance (Yahoo Finance), closing price |
| Commodities | yfinance (futures continuous contracts) |
| Cryptocurrency | CoinGecko historical prices API (free tier) |
| Forex | yfinance (Yahoo Finance FX) |
| Weather | Open-Meteo forecast API (temperature_2m_max, °F) |
| NBA | ESPN unofficial public API |

### Calibration Metrics

**Hit rate and ECE:** As in Studies 1 and 2 (Eq. 1 in main paper).

**Meta-knowledge ratio (μ = MEAD/MAD):**

The Soll–Klayman (2004) framework was applied to the 80% CI. The 80% CI
endpoints [L, U] are treated as the 10th and 90th percentiles of a symmetric
normal distribution centered on the midpoint, implying z = 1.2816.

For prediction i in domain d with outcome y_i:
- **AD_i** (Absolute Deviation) = |midpoint_i − y_i| / σ_d
  where midpoint_i = (L_i + U_i) / 2 and σ_d is the standard deviation of
  all outcomes in domain d
- **EAD_i** (Expected Absolute Deviation) = (half_width_i / σ_d)  
  where half_width_i = (U_i − L_i) / 2
- **MAD** = mean(AD_i) over all predictions in domain d
- **MEAD** = mean(EAD_i) over all predictions in domain d
- **μ** = MEAD / MAD

**Interpretation:** μ < 1 means stated CI widths are too narrow relative to
actual errors (overconfidence). μ > 1 means stated CI widths are too wide
(underconfidence). μ = 1 is perfect calibration.

[NEED DETAILS: Confirm exact normalization method for σ_d — whether prices are
first converted to percentage returns before computing σ, or whether raw prices
are used within each domain. The cross-unit nature of commodities (USD/oz,
USD/bbl, USD/MMBtu, USD/lb) makes a single raw-price σ problematic. Verify
from the script that generated Table 4 (μ values are currently hardcoded in
`build_ms.py` without a corresponding computation script).]

### Full Study 3 Domain Results

*From `study3/data/results/summary.csv`:*

| Model | Domain | n (rows) | n (resolved) | H@50 | H@80 | H@90 | ECE |
|-------|--------|-----------|-------------|------|------|------|-----|
| Claude | Stocks | 40 | 20 | 50.0% | 85.0% | 90.0% | 1.7% |
| Gemini | Stocks | 40 | 20 | 25.0% | 70.0% | 75.0% | 16.7% |
| GPT-4 | Stocks | 40 | 20 | 15.0% | 55.0% | 65.0% | 28.3% |
| Claude | Commodities | 10 | 5 | 20.0% | 40.0% | 40.0% | 40.0% |
| Gemini | Commodities | 10 | 5 | 20.0% | 40.0% | 40.0% | 40.0% |
| GPT-4 | Commodities | 10 | 5 | 20.0% | 40.0% | 40.0% | 40.0% |
| Claude | Crypto | 20 | 5 | 80.0% | 100.0% | 100.0% | 20.0% |
| Gemini | Crypto | 20 | 5 | 20.0% | 80.0% | 100.0% | 13.3% |
| GPT-4 | Crypto | 20 | 5 | 20.0% | 100.0% | 100.0% | 20.0% |
| Claude | Forex | 16 | 8 | 37.5% | 75.0% | 75.0% | 10.8% |
| Gemini | Forex | 16 | 8 | 50.0% | 62.5% | 75.0% | 10.8% |
| GPT-4 | Forex | 16 | 8 | 25.0% | 25.0% | 37.5% | 44.2% |
| Claude | Weather | 60 | 30 | 73.3% | 86.7% | 90.0% | 10.0% |
| Gemini | Weather | 60 | 30 | 66.7% | 83.3% | 86.7% | 7.8% |
| GPT-4 | Weather | 60 | 30 | 46.7% | 76.7% | 80.0% | 5.5% |
| All | NBA | 13 | 0 | — | — | — | — |

**Note on n (rows) vs. n (resolved):** The `summary.csv` file reports n as
the total number of prediction rows in `scored.csv`, including both the
March 25→26 (resolved) and March 26→27 (unresolved) prediction dates.
Hit rates and ECE in the table are computed only over resolved predictions.
The main paper reports the correct resolved n values.

### Data File Location

`study3/data/predictions/` — JSON prediction files, named
`{model}_{domain}_{item}_{date}.json`  
`study3/data/results/scored.csv` — all prediction rows with hit indicators  
`study3/data/results/summary.csv` — domain-level hit rates and ECE

---

## Robustness Notes (All Studies)

- **Retry logic:** Each API call was retried up to 3 times with exponential
  backoff (base 2s). Failed calls after 3 retries were logged and excluded.
- **JSON parsing:** Markdown fences in model responses were stripped before
  JSON parsing. Responses that could not be parsed after stripping were
  treated as failures.
- **Brier score:** A normalized Brier score was computed per prediction as
  `[(point_estimate − actual) / current_price]²`, providing a scale-free
  point-accuracy measure. Reported in `summary.csv` but not analyzed in the
  main paper.
- **Rate limiting:** A 0.3–0.5s sleep was inserted between API calls to
  avoid rate limit errors. Study 3 crypto data loss (5 of 10 outcomes) was
  due to CoinGecko free-tier rate limits during outcome fetching, not
  prediction collection.

---

*Last updated: April 2, 2026*
