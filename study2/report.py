"""
Generate overconfidence_report.md summarising experiment results.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from rich.console import Console

console = Console(legacy_windows=False)

RESULTS_DIR = Path("data/results")
SCORED_FILE = RESULTS_DIR / "scored.csv"
SUMMARY_FILE = RESULTS_DIR / "summary.csv"
REPORT_FILE = Path("overconfidence_report.md")

CONFIDENCE_LEVELS = [50, 80, 90]

CHART_FILES = {
    "calibration": "data/results/calibration_curves.png",
    "brier": "data/results/brier_scores.png",
    "heatmap": "data/results/ticker_heatmap.png",
    "ci_widths": "data/results/ci_widths.png",
}


def _pct(v) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{v * 100:.1f}%"


def _fmt(v, decimals=4) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{v:.{decimals}f}"


def calibration_verdict(hit_rate: float, stated: float) -> str:
    if pd.isna(hit_rate):
        return "N/A"
    diff = hit_rate - stated
    if diff < -0.15:
        return "severely overconfident"
    if diff < -0.05:
        return "overconfident"
    if diff > 0.15:
        return "underconfident"
    if diff > 0.05:
        return "slightly underconfident"
    return "well-calibrated"


def aggregate_by_model(summary: pd.DataFrame) -> pd.DataFrame:
    """Compute weighted-average calibration metrics per model across all windows."""
    rows = []
    for model, grp in summary.groupby("model"):
        w = grp["n_predictions"]
        total_n = w.sum()
        row = {"model": model, "n_predictions": total_n}
        for col in ["hit_rate_50", "hit_rate_80", "hit_rate_90", "mean_brier_score", "mean_ece"]:
            if col in grp.columns:
                valid = grp[col].notna()
                if valid.any():
                    row[col] = (grp.loc[valid, col] * w[valid]).sum() / w[valid].sum()
                else:
                    row[col] = float("nan")
        rows.append(row)
    return pd.DataFrame(rows).sort_values("model").reset_index(drop=True)


def generate_report(config: dict):
    if not SCORED_FILE.exists() or not SUMMARY_FILE.exists():
        console.print("[red]Scored data not found. Run score.py first.[/red]")
        return

    df = pd.read_csv(SCORED_FILE)
    summary = pd.read_csv(SUMMARY_FILE)
    today = date.today().isoformat()

    tickers = config.get("tickers", [])
    windows = sorted(summary["window_days"].unique().tolist())
    windows_str = ", ".join(str(w) for w in windows)
    models = sorted(df["model"].unique())

    model_summary = aggregate_by_model(summary)

    lines = []

    # ── Header ───────────────────────────────────────────────────────────────
    lines += [
        "# AI Model Overconfidence Report — Stock Price Predictions",
        "",
        f"**Generated:** {today}  ",
        f"**Prediction windows tested:** {windows_str} days  ",
        f"**Tickers:** {', '.join(tickers)}  ",
        f"**Models evaluated:** {', '.join(models)}  ",
        "",
        "---",
        "",
    ]

    # ── Overall summary table (one row per model) ─────────────────────────
    lines += [
        "## Summary: Calibration Metrics (All Windows Combined)",
        "",
        "A well-calibrated model's empirical hit rates should match its stated confidence levels.",
        "Hit rates **below** stated confidence indicate **overconfidence** (intervals too narrow).",
        "Metrics are weighted by number of predictions in each window.",
        "",
        "| Model | N | Hit@50% | Hit@80% | Hit@90% | Mean Brier | Mean ECE |",
        "|-------|---|---------|---------|---------|------------|----------|",
    ]

    for _, row in model_summary.iterrows():
        lines.append(
            f"| {row['model']} "
            f"| {int(row['n_predictions'])} "
            f"| {_pct(row.get('hit_rate_50'))} "
            f"| {_pct(row.get('hit_rate_80'))} "
            f"| {_pct(row.get('hit_rate_90'))} "
            f"| {_fmt(row.get('mean_brier_score'), 5)} "
            f"| {_fmt(row.get('mean_ece'), 4)} |"
        )

    lines += ["", "*(Lower Brier and ECE = better. Perfect calibration: 50%/80%/90% hit rates.)*", ""]

    # ── Window-by-window breakdown ────────────────────────────────────────
    lines += [
        "## Calibration by Prediction Horizon",
        "",
        "How hit rates change as the prediction window grows. "
        "Degrading hit rates at longer horizons confirm increasing overconfidence.",
        "",
    ]

    for level in CONFIDENCE_LEVELS:
        col = f"hit_rate_{level}"
        lines += [
            f"### {level}% Confidence Interval — Hit Rate by Window",
            "",
            "| Window (days) | " + " | ".join(models) + " |",
            "|---------------|" + "|".join(["-------"] * len(models)) + "|",
        ]
        for w in windows:
            cells = []
            for model in models:
                row = summary[(summary["model"] == model) & (summary["window_days"] == w)]
                val = row[col].values[0] if len(row) > 0 and col in row.columns else float("nan")
                cells.append(_pct(val))
            lines.append(f"| {w} | " + " | ".join(cells) + " |")
        lines.append("")

    # Brier score by window
    lines += [
        "### Mean Brier Score by Window",
        "",
        "| Window (days) | " + " | ".join(models) + " |",
        "|---------------|" + "|".join(["-------"] * len(models)) + "|",
    ]
    for w in windows:
        cells = []
        for model in models:
            row = summary[(summary["model"] == model) & (summary["window_days"] == w)]
            val = row["mean_brier_score"].values[0] if len(row) > 0 else float("nan")
            cells.append(_fmt(val, 5))
        lines.append(f"| {w} | " + " | ".join(cells) + " |")
    lines.append("")

    # ── Key findings (one section per model) ─────────────────────────────
    lines += ["## Key Findings", ""]

    for _, row in model_summary.iterrows():
        model = row["model"]
        lines.append(f"### {model}")

        for level in CONFIDENCE_LEVELS:
            hr = row.get(f"hit_rate_{level}")
            if not pd.isna(hr):
                v = calibration_verdict(hr, level / 100.0)
                lines.append(f"- **{level}% CI:** {v} — hit rate {_pct(hr)} vs stated {level}%")

        ece = row.get("mean_ece")
        if not pd.isna(ece):
            if ece > 0.15:
                lines.append(f"- **High ECE ({_fmt(ece)})** — substantial miscalibration overall")
            elif ece > 0.07:
                lines.append(f"- Moderate ECE ({_fmt(ece)}) — noticeable miscalibration")
            else:
                lines.append(f"- Low ECE ({_fmt(ece)}) — relatively well-calibrated")

        # Window trend note
        window_rows = summary[summary["model"] == model].sort_values("window_days")
        if len(window_rows) >= 2:
            hr80_short = window_rows.iloc[0]["hit_rate_80"]
            hr80_long = window_rows.iloc[-1]["hit_rate_80"]
            w_short = int(window_rows.iloc[0]["window_days"])
            w_long = int(window_rows.iloc[-1]["window_days"])
            if not pd.isna(hr80_short) and not pd.isna(hr80_long):
                direction = "degrades" if hr80_long < hr80_short else "improves"
                lines.append(
                    f"- 80% CI hit rate {direction} from {_pct(hr80_short)} at {w_short}d "
                    f"to {_pct(hr80_long)} at {w_long}d"
                )

        lines.append("")

    # ── Per-ticker breakdown ──────────────────────────────────────────────
    lines += ["## Per-Ticker Breakdown (80% CI Hit Rate, All Windows)", ""]
    pivot_rows = [
        "| Ticker | " + " | ".join(models) + " |",
        "|--------|" + "|".join(["--------"] * len(models)) + "|",
    ]
    for ticker in tickers:
        cells = []
        for model in models:
            sub = df[(df["model"] == model) & (df["ticker"] == ticker)]["hit_80"].dropna()
            cells.append(_pct(sub.mean()) if len(sub) > 0 else "N/A")
        pivot_rows.append(f"| {ticker} | " + " | ".join(cells) + " |")
    lines += pivot_rows
    lines += [""]

    # ── Charts ────────────────────────────────────────────────────────────
    lines += ["## Charts", ""]
    chart_descriptions = {
        "calibration": "**Calibration Curves** — stated confidence vs empirical hit rate. Points below the diagonal indicate overconfidence.",
        "brier": "**Brier Scores** — normalised mean squared percentage error of point estimates. Lower is better.",
        "heatmap": "**Per-Ticker Heatmap** — hit rate at 80% CI per model and ticker. Red cells indicate severe overconfidence.",
        "ci_widths": "**Confidence Interval Width Distributions** — how wide each model's intervals are as a percentage of the current price.",
    }
    for key, desc in chart_descriptions.items():
        path = CHART_FILES[key]
        if Path(path).exists():
            lines += [desc, "", f"![{key}]({path})", ""]
        else:
            lines += [f"*{desc} (chart not yet generated — run visualize.py)*", ""]

    # ── Methodology ───────────────────────────────────────────────────────
    lines += [
        "---",
        "## Methodology",
        "",
        "1. **Collection (backtest)**: Each model was given a historical price (date withheld) and asked for a point estimate plus 50/80/90% confidence intervals.",
        f"2. **Windows tested**: {windows_str} days — stratified sampling across prediction horizons.",
        "3. **Hit rate**: Fraction of predictions where the actual price fell within the stated interval.",
        "4. **Brier score**: Mean squared percentage error `((predicted - actual) / actual)²` for point estimates.",
        "5. **ECE**: Mean absolute gap between stated confidence and empirical hit rate across all CI levels.",
        "",
        "*This experiment does not constitute financial advice.*",
    ]

    report_text = "\n".join(lines)
    REPORT_FILE.write_text(report_text, encoding="utf-8")
    console.print(f"[bold green]Report written to {REPORT_FILE}[/bold green]")


if __name__ == "__main__":
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    generate_report(config)
