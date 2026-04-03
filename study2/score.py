"""
Score model predictions: Brier scores, hit rates, and Expected Calibration Error (ECE).
Reads data/results/actuals.csv and writes data/results/scored.csv + summary stats.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from rich.console import Console
from rich.table import Table

console = Console(legacy_windows=False)

RESULTS_DIR = Path("data/results")
ACTUALS_FILE = RESULTS_DIR / "actuals.csv"
SCORED_FILE = RESULTS_DIR / "scored.csv"
SUMMARY_FILE = RESULTS_DIR / "summary.csv"

CONFIDENCE_LEVELS = [50, 80, 90]


def compute_hit(row: pd.Series, level: int) -> float | None:
    """1.0 if actual price fell within the CI, 0.0 if not, None if data missing."""
    actual = row["actual_price"]
    low = row[f"ci_{level}_low"]
    high = row[f"ci_{level}_high"]
    if pd.isna(actual) or pd.isna(low) or pd.isna(high):
        return None
    return 1.0 if low <= actual <= high else 0.0


def compute_brier_score(df: pd.DataFrame) -> pd.Series:
    """
    Brier score for point estimate: mean squared error normalised by current price.
    Lower is better.
    """
    valid = df.dropna(subset=["actual_price", "point_estimate"])
    if valid.empty:
        return pd.Series(dtype=float)
    # Use percentage error squared so scores are comparable across price levels
    pct_error = (valid["point_estimate"] - valid["actual_price"]) / valid["actual_price"]
    return pct_error ** 2


def compute_ece(stated_confidence: float, hit_rate: float, n: int) -> float:
    """
    Expected Calibration Error contribution for one bucket.
    ECE = |stated - empirical| weighted by n.
    Returns the absolute gap (caller aggregates).
    """
    return abs(stated_confidence / 100.0 - hit_rate)


def score(config: dict | None = None) -> pd.DataFrame:
    if not ACTUALS_FILE.exists():
        console.print(f"[red]Actuals file not found: {ACTUALS_FILE}. Run fetch_actuals first.[/red]")
        return pd.DataFrame()

    df = pd.read_csv(ACTUALS_FILE)
    has_actuals = df["actual_price"].notna()

    if not has_actuals.any():
        console.print("[yellow]No actual prices available yet — prediction windows may not have closed.[/yellow]")

    # --- Hit rate columns ---
    for level in CONFIDENCE_LEVELS:
        df[f"hit_{level}"] = df.apply(lambda r: compute_hit(r, level), axis=1)

    # --- Brier score (per-row) ---
    brier = compute_brier_score(df)
    df["brier_score"] = np.nan
    df.loc[brier.index, "brier_score"] = brier.values

    df.to_csv(SCORED_FILE, index=False)
    console.print(f"[bold]Saved scored data to {SCORED_FILE}[/bold] ({len(df)} rows)")

    # --- Summary per model x window ---
    summary_rows = []
    group_cols = ["model", "window_days"] if "window_days" in df.columns else ["model"]
    for keys, grp in df.groupby(group_cols):
        if isinstance(keys, tuple):
            model, window_days = keys
        else:
            model, window_days = keys, None
        row = {"model": model, "window_days": window_days, "n_predictions": len(grp)}
        for level in CONFIDENCE_LEVELS:
            hits = grp[f"hit_{level}"].dropna()
            hit_rate = hits.mean() if len(hits) > 0 else float("nan")
            row[f"hit_rate_{level}"] = round(hit_rate, 4) if not np.isnan(hit_rate) else float("nan")
            row[f"ece_{level}"] = round(compute_ece(level, hit_rate, len(hits)), 4) if not np.isnan(hit_rate) else float("nan")

        valid_brier = grp["brier_score"].dropna()
        row["mean_brier_score"] = round(valid_brier.mean(), 6) if len(valid_brier) > 0 else float("nan")

        eces = [row[f"ece_{l}"] for l in CONFIDENCE_LEVELS if not np.isnan(row[f"ece_{l}"])]
        row["mean_ece"] = round(np.mean(eces), 4) if eces else float("nan")

        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_FILE, index=False)
    console.print(f"[bold]Saved summary to {SUMMARY_FILE}[/bold]")

    # --- Pretty print ---
    _print_summary(summary)
    return df


def _print_summary(summary: pd.DataFrame):
    table = Table(title="Model Calibration Summary", show_lines=True)
    table.add_column("Model", style="bold cyan")
    table.add_column("Window", justify="right")
    table.add_column("N", justify="right")
    table.add_column("Hit@50%", justify="right")
    table.add_column("Hit@80%", justify="right")
    table.add_column("Hit@90%", justify="right")
    table.add_column("Brier (lower=better)", justify="right")
    table.add_column("ECE (lower=better)", justify="right")

    for _, row in summary.iterrows():
        def fmt(v):
            if pd.isna(v):
                return "[dim]N/A[/dim]"
            return f"{v:.3f}"

        window = str(int(row["window_days"])) + "d" if not pd.isna(row.get("window_days", float("nan"))) else "?"
        table.add_row(
            row["model"],
            window,
            str(int(row["n_predictions"])),
            fmt(row.get("hit_rate_50")),
            fmt(row.get("hit_rate_80")),
            fmt(row.get("hit_rate_90")),
            fmt(row.get("mean_brier_score")),
            fmt(row.get("mean_ece")),
        )

    console.print(table)

    console.print("\n[bold]Interpretation:[/bold]")
    console.print("  A well-calibrated model's hit rates should match stated confidence levels:")
    console.print("  Hit@50% ~0.50,  Hit@80% ~0.80,  Hit@90% ~0.90")
    console.print("  Hit rates consistently below stated confidence = [red]overconfident[/red]")
    console.print("  Hit rates consistently above stated confidence = [yellow]underconfident[/yellow]")


if __name__ == "__main__":
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    score(config)
