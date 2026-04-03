"""
Generate a markdown report summarizing calibration results across all domains.
"""
from datetime import date
from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console(legacy_windows=False)

RESULTS_DIR  = Path("data/results")
SUMMARY_FILE = RESULTS_DIR / "summary.csv"
REPORT_FILE  = Path("overconfidence_report.md")

CONFIDENCE_LEVELS = [50, 80, 90]


def generate_report():
    if not SUMMARY_FILE.exists():
        console.print(f"[red]{SUMMARY_FILE} not found. Run score.py first.[/red]")
        return

    summary = pd.read_csv(SUMMARY_FILE)
    domains = sorted(summary["domain"].unique())
    models  = sorted(summary["model"].unique())

    lines = [
        "# AI Model Overconfidence Report — Multi-Domain",
        "",
        f"**Generated:** {date.today().isoformat()}  ",
        f"**Domains:** {', '.join(domains)}  ",
        f"**Models:** {', '.join(models)}",
        "",
        "---",
        "",
        "## Overall Calibration Summary",
        "",
        "A well-calibrated model's empirical hit rates should match its stated confidence levels.  ",
        "Hit rates **below** stated confidence indicate **overconfidence** (intervals too narrow).",
        "",
    ]

    # Aggregate across domains
    scored = pd.read_csv(RESULTS_DIR / "scored.csv") if (RESULTS_DIR / "scored.csv").exists() else None

    if scored is not None and not scored.empty:
        agg_rows = []
        for model in models:
            sub = scored[scored["model"] == model]
            row_data = {"model": model}
            for level in CONFIDENCE_LEVELS:
                hits = sub[f"hit_{level}"].dropna()
                row_data[f"hit_{level}"] = hits.mean() if len(hits) else float("nan")
            agg_rows.append(row_data)

        lines.append("| Model | N | Hit@50% | Hit@80% | Hit@90% | Mean ECE |")
        lines.append("|-------|---|---------|---------|---------|----------|")
        for row in agg_rows:
            model = row["model"]
            sub   = scored[scored["model"] == model]
            n     = int(sub["actual_value"].notna().sum())
            eces  = [abs(l / 100 - row[f"hit_{l}"]) for l in CONFIDENCE_LEVELS
                     if not pd.isna(row[f"hit_{l}"])]
            mean_ece = sum(eces) / len(eces) if eces else float("nan")

            def pct(v):
                return f"{v:.1%}" if not pd.isna(v) else "N/A"

            lines.append(
                f"| {model} | {n} | {pct(row['hit_50'])} | {pct(row['hit_80'])} | "
                f"{pct(row['hit_90'])} | {pct(mean_ece)} |"
            )
        lines.append("")
        lines.append("*(Perfect calibration: 50%/80%/90% hit rates. Lower ECE = better.)*")
        lines.append("")

    # Per-domain breakdown
    lines += ["---", "", "## Per-Domain Breakdown", ""]

    for domain in domains:
        lines.append(f"### {domain.capitalize()}")
        lines.append("")
        dom_rows = summary[summary["domain"] == domain]

        lines.append("| Model | N | Hit@50% | Hit@80% | Hit@90% | ECE |")
        lines.append("|-------|---|---------|---------|---------|-----|")
        for _, row in dom_rows.iterrows():
            def pct(v):
                return f"{v:.1%}" if not pd.isna(v) else "N/A"
            lines.append(
                f"| {row['model']} | {int(row['n'])} | "
                f"{pct(row.get('hit_rate_50'))} | {pct(row.get('hit_rate_80'))} | "
                f"{pct(row.get('hit_rate_90'))} | {pct(row.get('mean_ece'))} |"
            )
        lines.append("")

        # Narrative per model
        for _, row in dom_rows.iterrows():
            findings = []
            for level in CONFIDENCE_LEVELS:
                hr = row.get(f"hit_rate_{level}")
                if not pd.isna(hr):
                    gap = level / 100 - hr
                    if gap > 0.15:
                        findings.append(f"{level}% CI: severely overconfident (hit {hr:.1%} vs stated {level}%)")
                    elif gap > 0.05:
                        findings.append(f"{level}% CI: moderately overconfident (hit {hr:.1%} vs stated {level}%)")
                    elif gap < -0.05:
                        findings.append(f"{level}% CI: underconfident (hit {hr:.1%} vs stated {level}%)")
                    else:
                        findings.append(f"{level}% CI: well-calibrated (hit {hr:.1%} vs stated {level}%)")
            if findings:
                lines.append(f"**{row['model']}**: " + "; ".join(findings) + "  ")
        lines.append("")

    # Charts
    lines += [
        "---",
        "## Charts",
        "",
        "**Calibration Curves** — stated confidence vs empirical hit rate by domain.",
        "",
        "![calibration](data/results/calibration_curves.png)",
        "",
        "**ECE Heatmap** — miscalibration by model and domain.",
        "",
        "![ece](data/results/ece_heatmap.png)",
        "",
        "**Brier Scores** — normalised point estimate accuracy per domain.",
        "",
        "![brier](data/results/brier_scores.png)",
        "",
        "**CI Width Distributions** — width of confidence intervals as % of reference value.",
        "",
        "![ci_widths](data/results/ci_widths.png)",
        "",
        "---",
        "## Methodology",
        "",
        "1. **Domains**: Stocks (yfinance), Crypto (CoinGecko), Weather (Open-Meteo), "
        "NBA (ESPN), Forex (yfinance), Commodities (yfinance).",
        "2. **Collection**: Each model is prompted with current context and asked for a point "
        "estimate plus 50/80/90% confidence intervals.",
        "3. **Ground truth**: Actual outcomes fetched the following day from each domain's API.",
        "4. **Hit rate**: Fraction of predictions where the actual value fell within the stated interval.",
        "5. **Brier score**: Normalised mean squared error `((predicted - actual) / reference)²`.",
        "6. **ECE**: Mean absolute gap between stated confidence and empirical hit rate.",
        "",
        "*This experiment does not constitute financial or any other professional advice.*",
    ]

    REPORT_FILE.write_text("\n".join(lines))
    console.print(f"[bold]Report saved -> {REPORT_FILE}[/bold]")


if __name__ == "__main__":
    generate_report()
