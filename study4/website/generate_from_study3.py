"""
generate_from_study3.py — Export Study 3 data to website JSON.

Reads study3/data/results/scored.csv, computes mu/accuracy from raw CI widths
using the Soll & Klayman (2004) framework, writes website/data/study3/domains.json.

Run from study4/website/:
  python generate_from_study3.py
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

STUDY3_SCORED = Path(__file__).parent.parent.parent / "study3" / "data" / "results" / "scored.csv"
OUTPUT_DIR = Path(__file__).parent / "data" / "study3"

SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)
Z_90 = 1.645

DOMAIN_ORDER = ["stocks", "crypto", "forex", "weather", "commodities"]
DOMAIN_LABELS = {
    "stocks": "Stocks",
    "crypto": "Crypto",
    "forex": "Forex",
    "weather": "Weather",
    "commodities": "Commodities",
}


def compute_mad_mead(row):
    """Compute Soll & Klayman MAD/MEAD building blocks for a single row."""
    try:
        actual = float(row["actual_value"])
        pred = float(row["point_estimate"])
        ref = float(row["current_value"])
        lo = float(row["ci_90_low"])
        hi = float(row["ci_90_high"])
    except (TypeError, ValueError):
        return pd.Series([None, None], index=["norm_abs_dev", "norm_expected_abs_dev"])

    if any(math.isnan(v) for v in (actual, pred, ref, lo, hi)) or ref == 0:
        return pd.Series([None, None], index=["norm_abs_dev", "norm_expected_abs_dev"])

    norm_abs_dev = abs(actual - pred) / ref
    sigma_implied = (hi - lo) / (2 * Z_90)
    norm_expected_abs_dev = (sigma_implied * SQRT_2_OVER_PI) / ref
    return pd.Series([norm_abs_dev, norm_expected_abs_dev],
                     index=["norm_abs_dev", "norm_expected_abs_dev"])


def se(arr):
    """Standard error of the mean."""
    n = len(arr)
    if n < 2:
        return None
    return float(arr.std(ddof=1) / math.sqrt(n))


def aggregate(df):
    """Compute aggregate metrics for a DataFrame of resolved predictions."""
    n = len(df)
    if n == 0:
        return None

    result = {"n": n}

    # Hit rates at all 3 CI levels
    for level in [50, 80, 90]:
        col = f"hit_{level}"
        if col in df.columns:
            vals = df[col].dropna()
            if len(vals) > 0:
                result[f"hit_rate_{level}"] = round(float(vals.mean()), 4)
                result[f"hit_rate_{level}_se"] = round(se(vals), 4) if se(vals) is not None else None
            else:
                result[f"hit_rate_{level}"] = None
                result[f"hit_rate_{level}_se"] = None

    # ECE at all 3 levels
    for level in [50, 80, 90]:
        target = level / 100.0
        hr = result.get(f"hit_rate_{level}")
        if hr is not None:
            result[f"ece_{level}"] = round(abs(target - hr), 4)

    # Mu and accuracy (from MAD/MEAD)
    nad = df["norm_abs_dev"].dropna()
    nead = df["norm_expected_abs_dev"].dropna()
    if len(nad) > 0 and float(nad.mean()) > 0:
        result["accuracy"] = round(float(nad.mean()), 6)
        result["accuracy_se"] = round(se(nad), 6) if se(nad) is not None else None
        if len(nead) > 0:
            result["mu"] = round(float(nead.mean()) / float(nad.mean()), 4)
            # Bootstrap-style SE approximation for mu
            if len(nad) >= 2:
                mu_vals = nead.values / nad.values
                mu_vals = mu_vals[~pd.isna(mu_vals)]
                result["mu_se"] = round(se(pd.Series(mu_vals)), 4) if len(mu_vals) >= 2 else None
            else:
                result["mu_se"] = None
        else:
            result["mu"] = None
            result["mu_se"] = None
    else:
        result["accuracy"] = None
        result["accuracy_se"] = None
        result["mu"] = None
        result["mu_se"] = None

    # Brier
    brier = df["brier_score"].dropna()
    if len(brier) > 0:
        result["mean_brier"] = round(float(brier.mean()), 6)

    return result


def main():
    print(f"Reading {STUDY3_SCORED}")
    df = pd.read_csv(STUDY3_SCORED)
    print(f"  {len(df)} rows, models={sorted(df['model'].unique())}, domains={sorted(df['domain'].unique())}")

    # Filter to resolved predictions (non-null actual_value)
    resolved = df.dropna(subset=["actual_value"]).copy()
    print(f"  {len(resolved)} resolved predictions")

    # Exclude NBA (all unresolved)
    resolved = resolved[resolved["domain"] != "nba"]
    print(f"  {len(resolved)} after excluding NBA")

    # Compute MAD/MEAD
    mad_mead = resolved.apply(compute_mad_mead, axis=1)
    resolved = pd.concat([resolved, mad_mead], axis=1)

    # Build output
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source": "Study 3: Cross-Domain Calibration",
        "total_predictions": int(len(df)),
        "resolved_predictions": int(len(resolved)),
        "domains_ordered": DOMAIN_ORDER,
        "domain_labels": DOMAIN_LABELS,
        "models": {},
    }

    models = sorted(resolved["model"].unique())
    for m in models:
        mdf = resolved[resolved["model"] == m]

        # Aggregate across all domains
        agg = aggregate(mdf)

        # Per-domain breakdown
        domains = {}
        for d in DOMAIN_ORDER:
            ddf = mdf[mdf["domain"] == d]
            if len(ddf) == 0:
                domains[d] = {"n": 0, "status": "no_data"}
                continue
            domain_agg = aggregate(ddf)
            if domain_agg:
                domain_agg["status"] = "active"
                domains[d] = domain_agg

        output["models"][m] = {
            "aggregate": agg,
            "domains": domains,
        }

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "domains.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWritten -> {out_path}")

    # Print summary
    for m in models:
        agg = output["models"][m]["aggregate"]
        print(f"  {m}: n={agg['n']}, hit90={agg.get('hit_rate_90', '?')}, "
              f"mu={agg.get('mu', '?')}, acc={agg.get('accuracy', '?')}")


if __name__ == "__main__":
    main()
