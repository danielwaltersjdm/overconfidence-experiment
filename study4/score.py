"""
score.py — Study 4 scoring.

Reads data/actuals/actuals.csv, computes hit rates and Brier scores,
writes data/results/scored.csv and data/results/summary.csv.

Schema is consistent with Study 3's score.py. Added columns:
  - horizon / horizon_days (from Study 2 multi-horizon design)

Run from study4/ directory.
"""

import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console(legacy_windows=False)

BASE_DIR     = Path(__file__).parent
ACTUALS_FILE = BASE_DIR / "data" / "actuals" / "actuals.csv"
RESULTS_DIR  = BASE_DIR / "data" / "results"
SCORED_FILE  = RESULTS_DIR / "scored.csv"
SUMMARY_FILE = RESULTS_DIR / "summary.csv"

CONFIDENCE_LEVELS = [90]


def compute_hit(row: pd.Series, level: int) -> float | None:
    actual = row["actual_value"]
    low    = row[f"ci_{level}_low"]
    high   = row[f"ci_{level}_high"]
    if pd.isna(actual) or pd.isna(low) or pd.isna(high):
        return None
    return 1.0 if float(low) <= float(actual) <= float(high) else 0.0


def compute_brier(row: pd.Series) -> float | None:
    """
    Normalised squared error: ((point_estimate - actual) / current_value)^2.
    Consistent with Studies 1–3 formula.
    """
    actual = row["actual_value"]
    pred   = row["point_estimate"]
    ref    = row["current_value"]
    try:
        actual, pred, ref = float(actual), float(pred), float(ref)
    except (TypeError, ValueError):
        return None
    if ref == 0 or np.isnan(actual) or np.isnan(pred) or np.isnan(ref):
        return None
    return ((pred - actual) / ref) ** 2


def score() -> pd.DataFrame:
    if not ACTUALS_FILE.exists():
        console.print(f"[red]Actuals file not found: {ACTUALS_FILE}. Run fetch_actuals.py first.[/red]")
        return pd.DataFrame()

    df = pd.read_csv(ACTUALS_FILE)
    resolved = df[df["status"] == "resolved"].copy()

    if resolved.empty:
        console.print("[yellow]No resolved actuals yet — prediction windows may not have closed.[/yellow]")
        return pd.DataFrame()

    for level in CONFIDENCE_LEVELS:
        resolved[f"hit_{level}"] = resolved.apply(lambda r: compute_hit(r, level), axis=1)

    resolved["brier_score"] = resolved.apply(compute_brier, axis=1)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    resolved.to_csv(SCORED_FILE, index=False)
    console.print(f"[bold]Saved scored data → {SCORED_FILE}[/bold] ({len(resolved)} rows)")

    # ── Summary: model × domain × horizon ─────────────────────────────────────
    summary_rows = []
    for (model, domain, horizon), grp in resolved.groupby(["model", "domain", "horizon"]):
        row = {"model": model, "domain": domain, "horizon": horizon, "n": len(grp)}
        for level in CONFIDENCE_LEVELS:
            hits     = grp[f"hit_{level}"].dropna()
            hit_rate = hits.mean() if len(hits) > 0 else float("nan")
            row[f"hit_rate_{level}"] = round(hit_rate, 4)
            row[f"ece_{level}"]      = (
                round(abs(level / 100.0 - hit_rate), 4)
                if not np.isnan(hit_rate) else float("nan")
            )
        valid_brier    = grp["brier_score"].dropna()
        row["mean_brier"] = round(valid_brier.mean(), 6) if len(valid_brier) > 0 else float("nan")
        eces = [row[f"ece_{l}"] for l in CONFIDENCE_LEVELS if not np.isnan(row[f"ece_{l}"])]
        row["mean_ece"] = round(np.mean(eces), 4) if eces else float("nan")
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values(["domain", "horizon", "model"])
    summary.to_csv(SUMMARY_FILE, index=False)
    console.print(f"[bold]Saved summary → {SUMMARY_FILE}[/bold]")

    _print_summary(summary)
    return resolved


def _print_summary(summary: pd.DataFrame):
    table = Table(title="Study 4 — Calibration Summary by Model × Domain × Horizon", show_lines=True)
    for col in ("Domain", "Horizon", "Model", "N", "Hit@50%", "Hit@80%", "Hit@90%", "Brier", "ECE"):
        table.add_column(col, justify="right" if col in ("N", "Hit@50%", "Hit@80%", "Hit@90%", "Brier", "ECE") else "left")

    def fmt(v):
        return f"{v:.3f}" if not pd.isna(v) else "[dim]N/A[/dim]"

    for _, row in summary.iterrows():
        table.add_row(
            row["domain"], row["horizon"], row["model"], str(int(row["n"])),
            fmt(row.get("hit_rate_50")), fmt(row.get("hit_rate_80")), fmt(row.get("hit_rate_90")),
            fmt(row.get("mean_brier")),  fmt(row.get("mean_ece")),
        )

    console.print(table)
    console.print("\nPerfect calibration: Hit@50%=0.50, Hit@80%=0.80, Hit@90%=0.90")
    console.print("Hit rates below stated level = [red]overconfident[/red]")


if __name__ == "__main__":
    score()
