"""
generate_from_study5.py — Export Study 5 (MLB game outcomes) to website JSON.

Reads study5/data/results/scored.csv + study5/data/actuals/actuals.csv,
computes calibration metrics per (model, quantity), and writes
website/data/study5/sports.json.

Normalization note: Study 5 uses *quantity-level mean actual* as the
normalization denominator (rather than per-row actual). This keeps the
Soll & Klayman MAD/MEAD framework well-defined when individual actuals
can be 0 (e.g., total_home_runs has games with 0 HRs, which would make
abs_dev/actual undefined). mu = mead/mad is invariant to this choice.

Run from study4/website/:
  python generate_from_study5.py
"""

import csv
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd

STUDY5_SCORED = Path(__file__).parent.parent.parent / "study5" / "data" / "results" / "scored.csv"
STUDY5_ACTUALS = Path(__file__).parent.parent.parent / "study5" / "data" / "actuals" / "actuals.csv"
OUTPUT_DIR = Path(__file__).parent / "data" / "study5"

SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)
Z_90 = 1.645

QUANTITY_ORDER = ["total_runs", "total_strikeouts", "total_home_runs",
                  "duration_min", "attendance"]
QUANTITY_LABELS = {
    "total_runs":       "Total Runs",
    "total_strikeouts": "Total Strikeouts",
    "total_home_runs":  "Total Home Runs",
    "duration_min":     "Game Duration (min)",
    "attendance":       "Attendance",
}


def safe_se(s: pd.Series) -> float | None:
    s = s.dropna()
    if len(s) < 2:
        return None
    return float(s.std(ddof=1) / math.sqrt(len(s)))


def compute_stats(df: pd.DataFrame, mean_actual: float) -> dict:
    """Compute calibration metrics for one (model, quantity) group."""
    n = len(df)
    if n == 0:
        return {"n": 0, "status": "no_data"}

    hr90 = float(df["hit_90"].mean())
    ece90 = abs(0.90 - hr90)

    # Use mean_actual as the normalization denominator (not per-row actual)
    # so the metric is well-defined when individual actuals can be 0.
    abs_dev = (df["actual"] - df["point_estimate"]).abs()
    nad = abs_dev / mean_actual

    ci_widths = (df["ci_90_high"] - df["ci_90_low"])
    sigma_implied = ci_widths / (2 * Z_90)
    expected_abs_dev = sigma_implied * SQRT_2_OVER_PI
    nead = expected_abs_dev / mean_actual

    mad = float(nad.mean())
    mead = float(nead.mean())
    mu = mead / mad if mad > 0 else None

    # Standard errors
    hr90_se = math.sqrt(hr90 * (1 - hr90) / n) if n > 0 else None
    acc_se = safe_se(nad)
    # Delta-method SE for mu
    mu_se = None
    if mad > 0 and mead > 0 and n > 1:
        sd_nad = float(nad.std(ddof=1))
        sd_nead = float(nead.std(ddof=1))
        paired = pd.concat([nad, nead], axis=1).dropna()
        if len(paired) > 1:
            cov = float(paired.iloc[:,0].cov(paired.iloc[:,1]))
        else:
            cov = 0.0
        var_ratio = (sd_nad/mad)**2 + (sd_nead/mead)**2 - 2*cov/(mad*mead)
        if var_ratio > 0:
            mu_se = float(mu * math.sqrt(var_ratio / n))

    return {
        "n":                n,
        "hit_rate_90":      round(hr90, 4),
        "ece_90":           round(ece90, 4),
        "mu":               round(mu, 4) if mu is not None else None,
        "accuracy":         round(mad, 4),
        "mean_ci_width":    round(float(ci_widths.mean()), 2),
        "hit_rate_90_se":   round(hr90_se, 4) if hr90_se is not None else None,
        "accuracy_se":      round(acc_se, 6) if acc_se is not None else None,
        "mu_se":            round(mu_se, 4) if mu_se is not None else None,
        "status":           "active",
    }


def aggregate_across_quantities(per_q_stats: dict, scored: pd.DataFrame,
                                quantity_means: dict, model: str) -> dict:
    """Pool across all quantities. We average normalized metrics, weighted by n."""
    quantities = [q for q in QUANTITY_ORDER if per_q_stats.get(q, {}).get("status") == "active"]
    if not quantities:
        return {"n": 0, "status": "no_data"}

    # Re-normalize each row by its quantity's mean_actual so we can combine.
    sub = scored[scored["model"] == model].copy()
    sub = sub[sub["quantity"].isin(quantities)]
    sub["_mean_q"] = sub["quantity"].map(quantity_means)
    sub["_nad"] = (sub["actual"] - sub["point_estimate"]).abs() / sub["_mean_q"]
    sub["_nead"] = ((sub["ci_90_high"] - sub["ci_90_low"]) / (2*Z_90)) * SQRT_2_OVER_PI / sub["_mean_q"]

    n = len(sub)
    hr90 = float(sub["hit_90"].mean())
    mad = float(sub["_nad"].mean())
    mead = float(sub["_nead"].mean())
    mu = mead / mad if mad > 0 else None

    hr90_se = math.sqrt(hr90 * (1 - hr90) / n) if n > 0 else None
    acc_se = safe_se(sub["_nad"])
    mu_se = None
    if mad > 0 and mead > 0 and n > 1:
        sd_nad = float(sub["_nad"].std(ddof=1))
        sd_nead = float(sub["_nead"].std(ddof=1))
        paired = pd.concat([sub["_nad"], sub["_nead"]], axis=1).dropna()
        cov = float(paired.iloc[:,0].cov(paired.iloc[:,1])) if len(paired) > 1 else 0.0
        var_ratio = (sd_nad/mad)**2 + (sd_nead/mead)**2 - 2*cov/(mad*mead)
        if var_ratio > 0:
            mu_se = float(mu * math.sqrt(var_ratio / n))

    return {
        "n":              n,
        "hit_rate_90":    round(hr90, 4),
        "ece_90":         round(abs(0.90 - hr90), 4),
        "mu":             round(mu, 4) if mu is not None else None,
        "accuracy":       round(mad, 4),
        "hit_rate_90_se": round(hr90_se, 4) if hr90_se is not None else None,
        "accuracy_se":    round(acc_se, 6) if acc_se is not None else None,
        "mu_se":          round(mu_se, 4) if mu_se is not None else None,
        "status":         "active",
    }


def main():
    print(f"Reading {STUDY5_SCORED}")
    scored = pd.read_csv(STUDY5_SCORED)
    print(f"  {len(scored)} scored rows")

    # Audit actuals for pending/resolved counts
    print(f"Reading {STUDY5_ACTUALS}")
    pending_games = []
    resolved_games = 0
    with open(STUDY5_ACTUALS) as f:
        for row in csv.DictReader(f):
            if row["status"] == "resolved":
                resolved_games += 1
            elif row["status"] == "pending":
                pending_games.append({
                    "game_pk":   row["game_pk"],
                    "game_date": row["game_date"],
                    "away_team": row["away_team"],
                    "home_team": row["home_team"],
                    "note":      row.get("note", ""),
                })
    total_games = resolved_games + len(pending_games)
    print(f"  {resolved_games}/{total_games} games resolved ({len(pending_games)} pending)")

    # Compute per-quantity mean actual (for normalization)
    quantity_means = {}
    for q in QUANTITY_ORDER:
        sub = scored[scored["quantity"] == q]
        quantity_means[q] = float(sub["actual"].mean()) if len(sub) > 0 else None
    print(f"  mean actuals (used as norm denominators):")
    for q, m in quantity_means.items():
        print(f"    {q}: {m:.2f}")

    # Compute per (model, quantity) stats
    models = sorted(scored["model"].unique())
    output = {
        "generated_at":         datetime.utcnow().isoformat() + "Z",
        "source":               "Study 5: MLB Game Outcome Calibration",
        "total_games_scheduled": total_games,
        "resolved_games":        resolved_games,
        "missed_games":          pending_games,
        "quantities_ordered":   QUANTITY_ORDER,
        "quantity_labels":      QUANTITY_LABELS,
        "quantity_means":       {q: round(m, 2) if m is not None else None for q, m in quantity_means.items()},
        "models":               {},
    }

    for m in models:
        per_q = {}
        for q in QUANTITY_ORDER:
            sub = scored[(scored["model"] == m) & (scored["quantity"] == q)]
            if quantity_means.get(q):
                per_q[q] = compute_stats(sub, quantity_means[q])
            else:
                per_q[q] = {"n": 0, "status": "no_data"}
        agg = aggregate_across_quantities(per_q, scored, quantity_means, m)

        output["models"][m] = {
            "model_id":   m,  # display only
            "aggregate":  agg,
            "quantities": per_q,
        }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "sports.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten -> {out_path}")

    # Headline summary
    print("\n=== Headline calibration (aggregate across 5 quantities) ===")
    for m in models:
        agg = output["models"][m]["aggregate"]
        print(f"  {m}: n={agg['n']} hit90={agg.get('hit_rate_90')} mu={agg.get('mu')} accuracy={agg.get('accuracy')}")


if __name__ == "__main__":
    main()
