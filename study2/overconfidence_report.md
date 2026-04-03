# AI Model Overconfidence Report — Stock Price Predictions

**Generated:** 2026-03-31  
**Prediction windows tested:** 1, 2, 3, 6, 7, 18, 20, 21, 22 days  
**Tickers:** AAPL, NVDA, MSFT, AMZN, GOOGL, META, TSLA, AVGO, BRK-B, JPM, V, MA, BAC, GS, MS, WFC, AXP, BLK, SCHW, C, LLY, JNJ, UNH, ABBV, MRK, TMO, ABT, AMGN, ISRG, GILD, VRTX, REGN, ZTS, PFE, WMT, COST, PG, KO, PEP, MCD, SBUX, NKE, HD, LOW, TGT, DIS, XOM, CVX, GE, CAT, HON, RTX, LMT, DE, BA, UPS, ETN, MMM, ORCL, MU, AMD, QCOM, TXN, IBM, CSCO, ACN, CRM, ADBE, INTU, NOW, ANET, PANW, CRWD, T, VZ, NEE, PLD, AMT, EQIX, BKNG, NFLX, UBER, PYPL, MRVL, PLTR, SPGI, MCO, AON, ITW, ICE, CME, SYK, MDT, BSX, ELV, CI, ADI, USB, PNC, TFC  
**Models evaluated:** claude, gemini, gpt4  

---

## Summary: Calibration Metrics (All Windows Combined)

A well-calibrated model's empirical hit rates should match its stated confidence levels.
Hit rates **below** stated confidence indicate **overconfidence** (intervals too narrow).
Metrics are weighted by number of predictions in each window.

| Model | N | Hit@50% | Hit@80% | Hit@90% | Mean Brier | Mean ECE |
|-------|---|---------|---------|---------|------------|----------|
| claude | 7000 | 34.7% | 57.9% | 69.7% | 0.00411 | 0.1952 |
| gemini | 4747 | 41.1% | 67.1% | 77.6% | 0.00418 | 0.1166 |
| gpt4 | 7085 | 18.5% | 34.9% | 45.5% | 0.00395 | 0.4035 |

*(Lower Brier and ECE = better. Perfect calibration: 50%/80%/90% hit rates.)*

## Calibration by Prediction Horizon

How hit rates change as the prediction window grows. Degrading hit rates at longer horizons confirm increasing overconfidence.

### 50% Confidence Interval — Hit Rate by Window

| Window (days) | claude | gemini | gpt4 |
|---------------|-------|-------|-------|
| 1 | 52.2% | 49.5% | 32.6% |
| 2 | 41.2% | 29.9% | 18.3% |
| 3 | 36.8% | 32.9% | 21.8% |
| 6 | 31.4% | 41.8% | 14.3% |
| 7 | 30.2% | 34.8% | 17.1% |
| 18 | 27.6% | 40.2% | 13.9% |
| 20 | 33.8% | 52.6% | 17.5% |
| 21 | 19.0% | 28.5% | 9.5% |
| 22 | 28.4% | 45.5% | 12.3% |

### 80% Confidence Interval — Hit Rate by Window

| Window (days) | claude | gemini | gpt4 |
|---------------|-------|-------|-------|
| 1 | 80.5% | 78.5% | 55.2% |
| 2 | 64.5% | 59.2% | 40.0% |
| 3 | 58.0% | 52.9% | 37.2% |
| 6 | 56.0% | 71.7% | 34.5% |
| 7 | 55.7% | 62.7% | 32.0% |
| 18 | 46.2% | 59.8% | 27.2% |
| 20 | 53.5% | 73.9% | 30.2% |
| 21 | 41.4% | 58.6% | 21.6% |
| 22 | 51.2% | 80.1% | 24.4% |

### 90% Confidence Interval — Hit Rate by Window

| Window (days) | claude | gemini | gpt4 |
|---------------|-------|-------|-------|
| 1 | 88.5% | 86.6% | 66.7% |
| 2 | 74.9% | 68.3% | 48.1% |
| 3 | 73.6% | 67.3% | 47.0% |
| 6 | 70.8% | 81.2% | 46.3% |
| 7 | 68.5% | 77.5% | 45.1% |
| 18 | 56.8% | 70.1% | 36.8% |
| 20 | 64.8% | 81.8% | 40.1% |
| 21 | 57.4% | 70.3% | 31.4% |
| 22 | 59.7% | 87.2% | 33.5% |

### Mean Brier Score by Window

| Window (days) | claude | gemini | gpt4 |
|---------------|-------|-------|-------|
| 1 | 0.00029 | 0.00026 | 0.00030 |
| 2 | 0.00101 | 0.00077 | 0.00099 |
| 3 | 0.00132 | 0.00137 | 0.00132 |
| 6 | 0.00206 | 0.00157 | 0.00202 |
| 7 | 0.00268 | 0.00364 | 0.00257 |
| 18 | 0.00766 | 0.00955 | 0.00734 |
| 20 | 0.00728 | 0.00658 | 0.00692 |
| 21 | 0.00943 | 0.00860 | 0.00894 |
| 22 | 0.00699 | 0.00527 | 0.00689 |

## Key Findings

### claude
- **50% CI:** severely overconfident — hit rate 34.7% vs stated 50%
- **80% CI:** severely overconfident — hit rate 57.9% vs stated 80%
- **90% CI:** severely overconfident — hit rate 69.7% vs stated 90%
- **High ECE (0.1952)** — substantial miscalibration overall
- 80% CI hit rate degrades from 80.5% at 1d to 51.2% at 22d

### gemini
- **50% CI:** overconfident — hit rate 41.1% vs stated 50%
- **80% CI:** overconfident — hit rate 67.1% vs stated 80%
- **90% CI:** overconfident — hit rate 77.6% vs stated 90%
- Moderate ECE (0.1166) — noticeable miscalibration
- 80% CI hit rate improves from 78.5% at 1d to 80.1% at 22d

### gpt4
- **50% CI:** severely overconfident — hit rate 18.5% vs stated 50%
- **80% CI:** severely overconfident — hit rate 34.9% vs stated 80%
- **90% CI:** severely overconfident — hit rate 45.5% vs stated 90%
- **High ECE (0.4035)** — substantial miscalibration overall
- 80% CI hit rate degrades from 55.2% at 1d to 24.4% at 22d

## Per-Ticker Breakdown (80% CI Hit Rate, All Windows)

| Ticker | claude | gemini | gpt4 |
|--------|--------|--------|--------|
| AAPL | 56.0% | 76.0% | 28.0% |
| NVDA | 96.0% | 93.2% | 58.7% |
| MSFT | 66.7% | 80.0% | 58.7% |
| AMZN | 78.7% | 90.7% | 60.0% |
| GOOGL | 82.7% | 84.0% | 28.0% |
| META | 85.3% | 93.3% | 45.9% |
| TSLA | 97.3% | 98.6% | 72.0% |
| AVGO | 96.0% | 89.0% | 65.3% |
| BRK-B | 81.3% | 85.1% | 62.7% |
| JPM | 50.7% | 68.0% | 24.0% |
| V | 72.0% | 78.9% | 50.7% |
| MA | 61.3% | 68.0% | 21.3% |
| BAC | 28.6% | 50.0% | 13.0% |
| GS | 21.4% | 29.4% | 8.6% |
| MS | 41.4% | 47.1% | 14.3% |
| WFC | 51.4% | 57.4% | 22.9% |
| AXP | 25.7% | 39.1% | 17.1% |
| BLK | 31.4% | 31.4% | 13.2% |
| SCHW | 78.6% | 80.0% | 74.3% |
| C | 72.9% | 51.5% | 35.7% |
| LLY | 53.3% | 66.2% | 17.3% |
| JNJ | 69.3% | 89.3% | 61.3% |
| UNH | 71.4% | 91.4% | 58.0% |
| ABBV | 51.4% | 69.6% | 31.4% |
| MRK | 37.1% | 58.8% | 22.9% |
| TMO | 65.7% | 71.0% | 42.9% |
| ABT | 47.1% | 62.9% | 32.9% |
| AMGN | 62.9% | 75.7% | 40.6% |
| ISRG | 80.0% | 95.7% | 40.6% |
| GILD | 61.4% | 79.7% | 35.7% |
| VRTX | 78.6% | 66.7% | 42.0% |
| REGN | 84.3% | 94.3% | 45.7% |
| ZTS | 30.0% | 45.3% | 8.6% |
| PFE | 91.4% | 87.9% | 61.8% |
| WMT | 58.7% | 57.5% | 46.7% |
| COST | 82.7% | 95.0% | 66.2% |
| PG | 18.6% | 31.4% | 4.3% |
| KO | 51.4% | 65.7% | 20.0% |
| PEP | 40.0% | 71.4% | 21.4% |
| MCD | 77.1% | 85.7% | 55.1% |
| SBUX | 82.9% | 85.7% | 54.3% |
| NKE | 28.6% | 26.5% | 27.1% |
| HD | 38.6% | 51.4% | 20.3% |
| LOW | 22.9% | 42.9% | 15.7% |
| TGT | 85.7% | 82.4% | 75.7% |
| DIS | 50.0% | 88.6% | 28.6% |
| XOM | 85.3% | 87.5% | 53.3% |
| CVX | 72.9% | 94.3% | 54.3% |
| GE | 41.4% | 71.4% | 27.1% |
| CAT | 27.1% | 60.0% | 17.1% |
| HON | 85.4% | 77.1% | 37.1% |
| RTX | 62.9% | 62.9% | 57.1% |
| LMT | 36.1% | 57.1% | 18.6% |
| DE | 21.4% | 26.5% | 17.1% |
| BA | 50.0% | 68.6% | 25.7% |
| UPS | 34.3% | 40.0% | 20.0% |
| ETN | 61.4% | 77.1% | 23.5% |
| MMM | 38.6% | 60.6% | 21.7% |
| ORCL | 54.7% | 57.5% | 24.0% |
| MU | 82.7% | 74.4% | 36.0% |
| AMD | 98.6% | 85.7% | 53.7% |
| QCOM | 37.1% | 66.7% | 18.6% |
| TXN | 14.3% | 8.6% | 11.6% |
| IBM | 42.9% | 42.9% | 24.3% |
| CSCO | 98.6% | 100.0% | 74.3% |
| ACN | 50.0% | 55.9% | 32.9% |
| CRM | 71.4% | 82.9% | 36.2% |
| ADBE | 58.6% | 60.0% | 32.9% |
| INTU | 14.3% | 2.9% | 12.9% |
| NOW | 44.3% | 47.1% | 17.6% |
| ANET | 95.7% | 91.2% | 54.3% |
| PANW | 37.1% | 68.6% | 8.8% |
| CRWD | 25.7% | 52.9% | 17.4% |
| T | 85.7% | 58.8% | 42.0% |
| VZ | 61.4% | 60.0% | 20.0% |
| NEE | 72.9% | 85.3% | 63.8% |
| PLD | 51.4% | 70.6% | 30.0% |
| AMT | 44.3% | 70.6% | 32.9% |
| EQIX | 90.0% | 91.4% | 54.3% |
| BKNG | 50.0% | 60.0% | 22.9% |
| NFLX | 31.9% | 29.4% | 22.9% |
| UBER | 85.7% | 82.9% | 68.6% |
| PYPL | 95.7% | 90.9% | 57.1% |
| MRVL | 58.6% | 68.6% | 36.8% |
| PLTR | 51.4% | 62.9% | 21.7% |
| SPGI | 62.9% | 77.1% | 35.7% |
| MCO | 88.6% | 81.8% | 53.6% |
| AON | 74.3% | 64.7% | 36.2% |
| ITW | 44.3% | 52.9% | 32.9% |
| ICE | 81.4% | 82.9% | 40.0% |
| CME | 84.3% | 88.6% | 61.4% |
| SYK | 32.9% | 62.9% | 22.9% |
| MDT | 18.6% | 20.0% | 10.0% |
| BSX | 38.6% | 31.4% | 17.1% |
| ELV | 27.1% | 17.1% | 27.1% |
| CI | 32.9% | 62.9% | 17.1% |
| ADI | 22.9% | 50.0% | 20.0% |
| USB | 81.4% | 25.7% | 13.0% |
| PNC | 41.4% | 42.9% | 20.6% |
| TFC | 17.1% | 25.7% | 14.5% |

## Charts

**Calibration Curves** — stated confidence vs empirical hit rate. Points below the diagonal indicate overconfidence.

![calibration](data/results/calibration_curves.png)

**Brier Scores** — normalised mean squared percentage error of point estimates. Lower is better.

![brier](data/results/brier_scores.png)

**Per-Ticker Heatmap** — hit rate at 80% CI per model and ticker. Red cells indicate severe overconfidence.

![heatmap](data/results/ticker_heatmap.png)

**Confidence Interval Width Distributions** — how wide each model's intervals are as a percentage of the current price.

![ci_widths](data/results/ci_widths.png)

---
## Methodology

1. **Collection (backtest)**: Each model was given a historical price (date withheld) and asked for a point estimate plus 50/80/90% confidence intervals.
2. **Windows tested**: 1, 2, 3, 6, 7, 18, 20, 21, 22 days — stratified sampling across prediction horizons.
3. **Hit rate**: Fraction of predictions where the actual price fell within the stated interval.
4. **Brier score**: Mean squared percentage error `((predicted - actual) / actual)²` for point estimates.
5. **ECE**: Mean absolute gap between stated confidence and empirical hit rate across all CI levels.

*This experiment does not constitute financial advice.*