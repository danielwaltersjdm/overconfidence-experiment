# AI Model Overconfidence Report — Stock Price Predictions

**Generated:** 2026-03-24  
**Prediction window:** 1 days  
**Tickers:** NVDA, AAPL, MSFT, AMZN, GOOGL, META, AVGO, TSLA, BRK-B, WMT, LLY, JPM, XOM, V, JNJ, MU, MA, ORCL, COST, SPY  
**Models evaluated:** claude, gemini, gpt4  

---

## Summary: Calibration Metrics

A well-calibrated model's empirical hit rates should match its stated confidence levels.
Hit rates **below** stated confidence indicate **overconfidence** (intervals too narrow).

| Model | N | Hit@50% | Hit@80% | Hit@90% | Mean Brier | Mean ECE |
|-------|---|---------|---------|---------|------------|----------|
| claude | 100 | 30.0% | 58.0% | 73.0% | 0.00040 | 0.1967 |
| gemini | 100 | 29.0% | 58.0% | 65.0% | 0.00039 | 0.2267 |
| gpt4 | 100 | 20.0% | 31.0% | 38.0% | 0.00045 | 0.4367 |

*(Lower Brier and ECE = better. Perfect calibration: 50%/80%/90% hit rates.)*

## Key Findings

### claude
- 50% CI: severely overconfident (hit rate 30.0% vs stated 50%)
- 80% CI: severely overconfident (hit rate 58.0% vs stated 80%)
- 90% CI: severely overconfident (hit rate 73.0% vs stated 90%)
- **High ECE (0.1967)** — substantial miscalibration overall

### gemini
- 50% CI: severely overconfident (hit rate 29.0% vs stated 50%)
- 80% CI: severely overconfident (hit rate 58.0% vs stated 80%)
- 90% CI: severely overconfident (hit rate 65.0% vs stated 90%)
- **High ECE (0.2267)** — substantial miscalibration overall

### gpt4
- 50% CI: severely overconfident (hit rate 20.0% vs stated 50%)
- 80% CI: severely overconfident (hit rate 31.0% vs stated 80%)
- 90% CI: severely overconfident (hit rate 38.0% vs stated 90%)
- **High ECE (0.4367)** — substantial miscalibration overall

## Per-Ticker Breakdown (80% CI Hit Rate)

| Ticker | claude | gemini | gpt4 |
|--------|--------|--------|--------|
| NVDA | 100.0% | 100.0% | 40.0% |
| AAPL | 100.0% | 100.0% | 100.0% |
| MSFT | 0.0% | 0.0% | 0.0% |
| AMZN | 60.0% | 100.0% | 0.0% |
| GOOGL | 20.0% | 0.0% | 0.0% |
| META | 80.0% | 100.0% | 0.0% |
| AVGO | 80.0% | 80.0% | 20.0% |
| TSLA | 100.0% | 100.0% | 100.0% |
| BRK-B | 100.0% | 100.0% | 100.0% |
| WMT | 0.0% | 0.0% | 20.0% |
| LLY | 80.0% | 80.0% | 0.0% |
| JPM | 80.0% | 80.0% | 20.0% |
| XOM | 0.0% | 0.0% | 0.0% |
| V | 0.0% | 20.0% | 0.0% |
| JNJ | 100.0% | 100.0% | 100.0% |
| MU | 80.0% | 0.0% | 0.0% |
| MA | 0.0% | 0.0% | 0.0% |
| ORCL | 0.0% | 0.0% | 0.0% |
| COST | 100.0% | 100.0% | 100.0% |
| SPY | 80.0% | 100.0% | 20.0% |

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

1. **Collection**: Each model was prompted with today's price and asked for a point estimate plus 50/80/90% confidence intervals.
2. **Window**: Actual prices were fetched 1 days after each prediction date.
3. **Hit rate**: Fraction of predictions where the actual price fell within the stated interval.
4. **Brier score**: Mean squared percentage error `((predicted - actual) / actual)²` for point estimates.
5. **ECE**: Mean absolute gap between stated confidence and empirical hit rate across all CI levels.

*This experiment does not constitute financial advice.*