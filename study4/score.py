"""
score.py — Study 4 scoring.

Reads data/actuals/actuals.csv, computes hit rates, Brier scores,
and Soll & Klayman (2004) MAD/MEAD calibration metrics.
Writes data/results/scored.csv and data/results/summary.csv.

Per-row columns added for MAD/MEAD framework:
  - abs_dev: |actual - point_estimate|
  - norm_abs_dev: abs_dev / current_value  (building block for Accuracy)
  - expected_abs_dev: implied absolute deviation from 90% CI width
  - norm_expected_abs_dev: expected_abs_dev / current_value

Summary adds: mad (=Accuracy), mead, mu (=MEAD/MAD).

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

    # ── Soll & Klayman (2004) MAD/MEAD building blocks ───────────────────────
    SQRT_2_OVER_PI = np.sqrt(2.0 / np.pi)  # ≈ 0.7979
    Z_90 = 1.645  # z-score for 90% CI (two-tailed)

    def _mad_mead_cols(row):
        try:
            actual = float(row["actual_value"])
            pred   = float(row["point_estimate"])
            ref    = float(row["current_value"])
            lo     = float(row["ci_90_low"])
            hi     = float(row["ci_90_high"])
        except (TypeError, ValueError):
            return pd.Series([None, None, None, None],
                             index=["abs_dev", "norm_abs_dev",
                                    "expected_abs_dev", "norm_expected_abs_dev"])
        if any(np.isnan(v) for v in (actual, pred, ref, lo, hi)) or ref == 0:
            return pd.Series([None, None, None, None],
                             index=["abs_dev", "norm_abs_dev",
                                    "expected_abs_dev", "norm_expected_abs_dev"])
        abs_dev = abs(actual - pred)
        norm_abs_dev = abs_dev / ref
        sigma_implied = (hi - lo) / (2 * Z_90)
        expected_abs_dev = sigma_implied * SQRT_2_OVER_PI
        norm_expected_abs_dev = expected_abs_dev / ref
        return pd.Series([abs_dev, norm_abs_dev, expected_abs_dev, norm_expected_abs_dev],
                         index=["abs_dev", "norm_abs_dev",
                                "expected_abs_dev", "norm_expected_abs_dev"])

    mad_mead = resolved.apply(_mad_mead_cols, axis=1)
    resolved = pd.concat([resolved, mad_mead], axis=1)

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
        # Soll & Klayman (2004) metrics
        valid_nad = grp["norm_abs_dev"].dropna()
        valid_nead = grp["norm_expected_abs_dev"].dropna()
        mad = valid_nad.mean() if len(valid_nad) > 0 else float("nan")
        mead = valid_nead.mean() if len(valid_nead) > 0 else float("nan")
        row["mad"]  = round(mad, 6) if not np.isnan(mad) else float("nan")
        row["mead"] = round(mead, 6) if not np.isnan(mead) else float("nan")
        row["mu"]   = round(mead / mad, 4) if (not np.isnan(mad) and not np.isnan(mead) and mad > 0) else float("nan")
        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows).sort_values(["domain", "horizon", "model"])
    summary.to_csv(SUMMARY_FILE, index=False)
    console.print(f"[bold]Saved summary → {SUMMARY_FILE}[/bold]")

    _print_summary(summary)
    return resolved


def _print_summary(summary: pd.DataFrame):
    table = Table(title="Study 4 — Calibration Summary by Model × Domain × Horizon", show_lines=True)
    for col in ("Domain", "Horizon", "Model", "N", "Hit@90%", "Accuracy", "μ", "Brier", "ECE"):
        table.add_column(col, justify="right" if col not in ("Domain", "Horizon", "Model") else "left")

    def fmt(v):
        return f"{v:.4f}" if not pd.isna(v) else "[dim]N/A[/dim]"

    for _, row in summary.iterrows():
        mu_val = row.get("mu")
        mu_str = f"{mu_val:.3f}" if not pd.isna(mu_val) else "[dim]N/A[/dim]"
        if not pd.isna(mu_val):
            if mu_val < 0.85:
                mu_str = f"[red]{mu_val:.3f}[/red]"
            elif mu_val <= 1.15:
                mu_str = f"[green]{mu_val:.3f}[/green]"
        table.add_row(
            row["domain"], row["horizon"], row["model"], str(int(row["n"])),
            fmt(row.get("hit_rate_90")),
            fmt(row.get("mad")),
            mu_str,
            fmt(row.get("mean_brier")),
            fmt(row.get("mean_ece")),
        )

    console.print(table)
    console.print("\nμ (MEAD/MAD): <1 = [red]overconfident[/red], =1 = perfectly calibrated, >1 = underconfident")
    console.print("Accuracy = normalized MAD (lower is better)")


if __name__ == "__main__":
    score()
