"""
score.py — Study 5: score predictions against actuals.

Joins data/predictions/*.json with data/actuals/actuals.csv and computes,
for each (model x game x quantity):
  - hit_90:                 1 if CI contains actual, else 0
  - point_error:            |actual - point_estimate|
  - norm_abs_dev:           point_error / actual  (relative error)
  - norm_expected_abs_dev:  Soll & Klayman implied MEAD from CI width, normalized

Writes data/results/scored.csv (long-form, one row per model x game x quantity)
and data/results/summary.csv (one row per model x quantity with hit rates,
mu, accuracy, ECE).

Usage (from study5/):
  python score.py
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

BASE_DIR = Path(__file__).parent
PRED_DIR = BASE_DIR / "data" / "predictions"
ACTUALS_FILE = BASE_DIR / "data" / "actuals" / "actuals.csv"
RESULTS_DIR = BASE_DIR / "data" / "results"

QUANTITIES = ["total_runs", "total_strikeouts", "total_home_runs",
              "duration_min", "attendance"]

SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)
Z_90 = 1.645


def main():
    if not ACTUALS_FILE.exists():
        console.print(f"[red]No actuals file. Run fetch_actuals.py first.[/red]")
        return

    # Load actuals into dict keyed by game_pk
    actuals = {}
    with open(ACTUALS_FILE, "r", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "resolved":
                continue
            pk = int(row["game_pk"])
            try:
                actuals[pk] = {q: float(row[q]) for q in QUANTITIES}
            except (KeyError, ValueError):
                continue

    console.print(f"[bold]Resolved games:[/bold] {len(actuals)}")

    if not actuals:
        console.print("[yellow]No resolved games yet — nothing to score.[/yellow]")
        return

    # Build long-form scored records
    rows = []
    for f in sorted(PRED_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        d = json.loads(f.read_text())
        if d.get("status") != "collected":
            continue
        pk = d.get("game_pk")
        if pk not in actuals:
            continue
        for q in QUANTITIES:
            pred_block = d["predictions"].get(q, {})
            point = pred_block.get("point_estimate")
            ci = pred_block.get("90_ci", [None, None])
            if point is None or ci[0] is None or ci[1] is None:
                continue
            actual = actuals[pk][q]
            lo, hi = float(ci[0]), float(ci[1])
            point = float(point)

            hit_90 = 1.0 if (lo <= actual <= hi) else 0.0
            abs_dev = abs(actual - point)
            denom = max(abs(actual), 1e-9)
            norm_abs_dev = abs_dev / denom
            sigma_implied = (hi - lo) / (2 * Z_90)
            expected_abs_dev = sigma_implied * SQRT_2_OVER_PI
            norm_expected_abs_dev = expected_abs_dev / denom

            rows.append({
                "model":                  d["model"],
                "model_id":               d["model_id"],
                "game_pk":                pk,
                "game_date":              d.get("game_date"),
                "away_team":              d.get("away_team"),
                "home_team":              d.get("home_team"),
                "venue":                  d.get("venue"),
                "quantity":               q,
                "point_estimate":         point,
                "ci_90_low":              lo,
                "ci_90_high":             hi,
                "ci_width":               hi - lo,
                "actual":                 actual,
                "hit_90":                 hit_90,
                "abs_dev":                abs_dev,
                "norm_abs_dev":           norm_abs_dev,
                "expected_abs_dev":       expected_abs_dev,
                "norm_expected_abs_dev":  norm_expected_abs_dev,
            })

    if not rows:
        console.print("[yellow]No scoreable predictions for resolved games.[/yellow]")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scored = pd.DataFrame(rows)
    scored_path = RESULTS_DIR / "scored.csv"
    scored.to_csv(scored_path, index=False)
    console.print(f"  Wrote {scored_path} ({len(scored)} rows)")

    # Summary: per model x quantity
    summary_rows = []
    for (m, q), g in scored.groupby(["model", "quantity"]):
        n = len(g)
        hr90 = g["hit_90"].mean()
        ece90 = abs(0.90 - hr90)
        mad = g["norm_abs_dev"].mean()
        mead = g["norm_expected_abs_dev"].mean()
        mu = mead / mad if mad > 0 else float("nan")
        summary_rows.append({
            "model": m, "quantity": q, "n": n,
            "hit_rate_90": round(hr90, 4),
            "ece_90":      round(ece90, 4),
            "accuracy":    round(mad, 4),
            "mu":          round(mu, 4),
            "ci_width_mean": round(g["ci_width"].mean(), 2),
        })

    summary = pd.DataFrame(summary_rows)
    summary_path = RESULTS_DIR / "summary.csv"
    summary.to_csv(summary_path, index=False)
    console.print(f"  Wrote {summary_path}")

    # Pretty table
    tbl = Table(title="Study 5 — Calibration by Model × Quantity")
    for col in ["Quantity", "Model", "N", "Hit@90%", "ECE", "μ", "Accuracy", "CI width"]:
        tbl.add_column(col)
    for r in summary.sort_values(["quantity", "model"]).to_dict("records"):
        tbl.add_row(r["quantity"], r["model"], str(r["n"]),
                    f"{r['hit_rate_90']:.3f}", f"{r['ece_90']:.3f}",
                    f"{r['mu']:.3f}" if r['mu'] == r['mu'] else "—",
                    f"{r['accuracy']:.3f}", f"{r['ci_width_mean']:.1f}")
    console.print()
    console.print(tbl)


if __name__ == "__main__":
    main()
