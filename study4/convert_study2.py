"""
convert_study2.py — Convert Study 2 scored.csv into Study 4 format.

Reads study2/data/results/scored.csv, maps columns to Study 4 schema,
computes MAD/MEAD columns, and writes to study4/data/results/scored.csv.

Then runs export_data.py to generate website JSON.

Run from study4/ directory.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console

console = Console(legacy_windows=False)

STUDY2_SCORED = Path(__file__).parent.parent / "study2" / "data" / "results" / "scored.csv"
STUDY4_SCORED = Path(__file__).parent / "data" / "results" / "scored.csv"
STUDY4_RESULTS = Path(__file__).parent / "data" / "results"

SQRT_2_OVER_PI = np.sqrt(2.0 / np.pi)
Z_90 = 1.645

# Map window_days to horizon labels
HORIZON_MAP = {
    1: "1d", 2: "2d", 3: "3d", 6: "6d", 7: "7d",
    14: "14d", 18: "18d", 20: "20d", 21: "21d", 22: "22d", 30: "30d",
}


def convert():
    if not STUDY2_SCORED.exists():
        console.print(f"[red]Study 2 scored.csv not found: {STUDY2_SCORED}[/red]")
        return

    df = pd.read_csv(STUDY2_SCORED)
    console.print(f"[bold]Read Study 2 scored.csv:[/bold] {len(df)} rows")

    # Map columns to Study 4 schema
    out = pd.DataFrame()
    out["model"] = df["model"]
    out["domain"] = "stocks"
    out["item_id"] = df["ticker"]
    out["pred_date"] = df["pred_date"]
    out["horizon"] = df["window_days"].map(HORIZON_MAP)
    out["current_value"] = df["current_price"]
    out["point_estimate"] = df["point_estimate"]
    out["ci_90_low"] = df["ci_90_low"]
    out["ci_90_high"] = df["ci_90_high"]
    out["actual_value"] = df["actual_price"]
    out["status"] = "resolved"
    out["target_date"] = df["target_date"]
    out["actual_date"] = df["actual_date"]
    out["run"] = df["run"]

    # Carry over existing hit/brier columns
    out["hit_90"] = df["hit_90"]
    out["brier_score"] = df["brier_score"]

    # Compute MAD/MEAD building blocks
    out["abs_dev"] = np.abs(out["actual_value"] - out["point_estimate"])
    out["norm_abs_dev"] = out["abs_dev"] / out["current_value"]

    sigma_implied = (out["ci_90_high"] - out["ci_90_low"]) / (2 * Z_90)
    out["expected_abs_dev"] = sigma_implied * SQRT_2_OVER_PI
    out["norm_expected_abs_dev"] = out["expected_abs_dev"] / out["current_value"]

    # Handle edge cases
    mask = (out["current_value"] == 0) | out["current_value"].isna()
    out.loc[mask, ["norm_abs_dev", "norm_expected_abs_dev"]] = np.nan

    # Drop rows with unmapped horizons
    out = out.dropna(subset=["horizon"])

    STUDY4_RESULTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(STUDY4_SCORED, index=False)
    console.print(f"[bold green]Written Study 4 scored.csv:[/bold green] {len(out)} rows")
    console.print(f"  Path: {STUDY4_SCORED}")

    # Print summary
    console.print(f"\n  Models: {sorted(out['model'].unique())}")
    console.print(f"  Tickers: {out['item_id'].nunique()}")
    console.print(f"  Horizons: {sorted(out['horizon'].unique())}")
    console.print(f"  Date range: {out['pred_date'].min()} to {out['pred_date'].max()}")


if __name__ == "__main__":
    convert()
