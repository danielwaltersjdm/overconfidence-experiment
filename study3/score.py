"""
Score predictions: hit rates, Brier scores, and ECE.
Reads data/results/actuals.csv, writes scored.csv and summary.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console(legacy_windows=False)

RESULTS_DIR = Path("data/results")
ACTUALS_FILE = RESULTS_DIR / "actuals.csv"
SCORED_FILE  = RESULTS_DIR / "scored.csv"
SUMMARY_FILE = RESULTS_DIR / "summary.csv"

CONFIDENCE_LEVELS = [50, 80, 90]


def compute_hit(row: pd.Series, level: int) -> float | None:
    actual = row["actual_value"]
    low    = row[f"ci_{level}_low"]
    high   = row[f"ci_{level}_high"]
    if pd.isna(actual) or pd.isna(low) or pd.isna(high):
        return None
    return 1.0 if low <= actual <= high else 0.0


def compute_brier(row: pd.Series) -> float | None:
    """
    Normalised squared error: ((predicted - actual) / actual)^2.
    Works for any positive-valued quantity (prices, temperatures >0, scores).
    Returns None if data missing or current_value is zero.
    """
    actual = row["actual_value"]
    pred   = row["point_estimate"]
    ref    = row["current_value"]
    if pd.isna(actual) or pd.isna(pred) or pd.isna(ref) or ref == 0:
        return None
    return ((pred - actual) / ref) ** 2


def score() -> pd.DataFrame:
    if not ACTUALS_FILE.exists():
        console.print(f"[red]Actuals file not found: {ACTUALS_FILE}. Run fetch_actuals first.[/red]")
        return pd.DataFrame()

    df = pd.read_csv(ACTUALS_FILE)

    if df["actual_value"].isna().all():
        console.print("[yellow]No actuals available yet — prediction windows may not have closed.[/yellow]")

    for level in CONFIDENCE_LEVELS:
        df[f"hit_{level}"] = df.apply(lambda r: compute_hit(r, level), axis=1)

    df["brier_score"] = df.apply(compute_brier, axis=1)

    df.to_csv(SCORED_FILE, index=False)
    console.print(f"[bold]Saved scored data -> {SCORED_FILE}[/bold] ({len(df)} rows)")

    # Summary: per model × domain
    summary_rows = []
    for (model, domain), grp in df.groupby(["model", "domain"]):
        row = {"model": model, "domain": domain, "n": len(grp)}
        for level in CONFIDENCE_LEVELS:
            hits = grp[f"hit_{level}"].dropna()
            hit_rate = hits.mean() if len(hits) > 0 else float("nan")
            row[f"hit_rate_{level}"] = round(hit_rate, 4)
            row[f"ece_{level}"]      = round(abs(level / 100.0 - hit_rate), 4) if not np.isnan(hit_rate) else float("nan")

        valid_brier = grp["brier_score"].dropna()
        row["mean_brier"] = round(valid_brier.mean(), 6) if len(valid_brier) > 0 else float("nan")
        eces = [row[f"ece_{l}"] for l in CONFIDENCE_LEVELS if not np.isnan(row[f"ece_{l}"])]
        row["mean_ece"] = round(np.mean(eces), 4) if eces else float("nan")
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values(["domain", "model"])
    summary.to_csv(SUMMARY_FILE, index=False)
    console.print(f"[bold]Saved summary -> {SUMMARY_FILE}[/bold]")

    _print_summary(summary)
    return df


def _print_summary(summary: pd.DataFrame):
    table = Table(title="Calibration Summary by Model × Domain", show_lines=True)
    table.add_column("Domain",   style="bold")
    table.add_column("Model",    style="cyan")
    table.add_column("N",        justify="right")
    table.add_column("Hit@50%",  justify="right")
    table.add_column("Hit@80%",  justify="right")
    table.add_column("Hit@90%",  justify="right")
    table.add_column("Brier",    justify="right")
    table.add_column("ECE",      justify="right")

    def fmt(v):
        return f"{v:.3f}" if not pd.isna(v) else "[dim]N/A[/dim]"

    for _, row in summary.iterrows():
        table.add_row(
            row["domain"], row["model"], str(int(row["n"])),
            fmt(row.get("hit_rate_50")), fmt(row.get("hit_rate_80")), fmt(row.get("hit_rate_90")),
            fmt(row.get("mean_brier")),  fmt(row.get("mean_ece")),
        )

    console.print(table)
    console.print("\nPerfect calibration: Hit@50%=0.50, Hit@80%=0.80, Hit@90%=0.90")
    console.print("Hit rates below stated confidence = [red]overconfident[/red]")


if __name__ == "__main__":
    score()
