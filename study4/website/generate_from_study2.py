"""
generate_from_study2.py — Export Study 2 data to website JSON.

Reads study2/data/results/scored.csv, computes mu/accuracy/hit rates per
model x horizon x sector x item, writes to website/data/study2/.

Run from study4/website/:
  python generate_from_study2.py
"""

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

STUDY2_SCORED = Path(__file__).parent.parent.parent / "study2" / "data" / "results" / "scored.csv"
OUTPUT_DIR = Path(__file__).parent / "data" / "study2"

SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)
Z_90 = 1.645

HORIZON_MAP = {
    1: "1d", 2: "2d", 3: "3d", 6: "6d", 7: "7d",
    18: "18d", 20: "20d", 21: "21d", 22: "22d",
}
HORIZON_ORDER = ["1d", "2d", "3d", "6d", "7d", "18d", "20d", "21d", "22d"]

MODEL_MAP = {"gpt4": "gpt4o"}

SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "META": "Technology", "AVGO": "Technology",
    "ORCL": "Technology", "AMD": "Technology", "ACN": "Technology",
    "CSCO": "Technology", "ADBE": "Technology", "IBM": "Technology",
    "NOW": "Technology", "INTU": "Technology", "QCOM": "Technology",
    "TXN": "Technology", "CRM": "Technology", "PANW": "Technology",
    "ADI": "Technology", "KLAC": "Technology", "AMAT": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "MRVL": "Technology",
    "FTNT": "Technology", "IT": "Technology", "KEYS": "Technology",
    "LRCX": "Technology", "MU": "Technology", "ANET": "Technology",
    "CRWD": "Technology", "PLTR": "Technology", "CTSH": "Technology",
    "ON": "Technology",
    "BRK-B": "Financials", "JPM": "Financials", "V": "Financials",
    "MA": "Financials", "BAC": "Financials", "WFC": "Financials",
    "GS": "Financials", "AXP": "Financials", "BLK": "Financials",
    "SPGI": "Financials", "MS": "Financials", "SCHW": "Financials",
    "C": "Financials", "CB": "Financials", "ADP": "Financials",
    "CME": "Financials", "ICE": "Financials", "USB": "Financials",
    "PNC": "Financials", "AON": "Financials", "AJG": "Financials",
    "AFL": "Financials", "TRV": "Financials", "AIG": "Financials",
    "BK": "Financials", "MSCI": "Financials", "NDAQ": "Financials",
    "ALL": "Financials", "GPN": "Financials", "MCO": "Financials",
    "TFC": "Financials", "PYPL": "Financials",
    "LLY": "Healthcare", "UNH": "Healthcare", "JNJ": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare",
    "ABT": "Healthcare", "ISRG": "Healthcare", "AMGN": "Healthcare",
    "BMY": "Healthcare", "VRTX": "Healthcare", "GILD": "Healthcare",
    "REGN": "Healthcare", "BSX": "Healthcare", "SYK": "Healthcare",
    "CI": "Healthcare", "DHR": "Healthcare", "MCK": "Healthcare",
    "HCA": "Healthcare", "ZTS": "Healthcare", "DXCM": "Healthcare",
    "EW": "Healthcare", "BIIB": "Healthcare", "IDXX": "Healthcare",
    "A": "Healthcare", "GEHC": "Healthcare", "RMD": "Healthcare",
    "PFE": "Healthcare", "WST": "Healthcare", "MDT": "Healthcare",
    "ELV": "Healthcare",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "NFLX": "Consumer Discretionary",
    "MCD": "Consumer Discretionary", "BKNG": "Consumer Discretionary",
    "TJX": "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "LOW": "Consumer Discretionary", "CMG": "Consumer Discretionary",
    "ROST": "Consumer Discretionary", "ORLY": "Consumer Discretionary",
    "AZO": "Consumer Discretionary", "HLT": "Consumer Discretionary",
    "YUM": "Consumer Discretionary", "RCL": "Consumer Discretionary",
    "ABNB": "Consumer Discretionary", "TGT": "Consumer Discretionary",
    "DLTR": "Consumer Discretionary", "DG": "Consumer Discretionary",
    "TTWO": "Consumer Discretionary", "EA": "Consumer Discretionary",
    "TSCO": "Consumer Discretionary", "F": "Consumer Discretionary",
    "GM": "Consumer Discretionary", "LUV": "Consumer Discretionary",
    "DAL": "Consumer Discretionary", "UAL": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "UBER": "Consumer Discretionary",
    "DIS": "Communication Services",
    "PG": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "PM": "Consumer Staples",
    "MDLZ": "Consumer Staples", "CL": "Consumer Staples",
    "MO": "Consumer Staples", "KDP": "Consumer Staples",
    "KR": "Consumer Staples", "HSY": "Consumer Staples",
    "MNST": "Consumer Staples", "GIS": "Consumer Staples",
    "KMB": "Consumer Staples", "STZ": "Consumer Staples",
    "GE": "Industrials", "CAT": "Industrials", "HON": "Industrials",
    "UNP": "Industrials", "DE": "Industrials", "RTX": "Industrials",
    "FDX": "Industrials", "NSC": "Industrials", "PCAR": "Industrials",
    "GD": "Industrials", "EMR": "Industrials", "JCI": "Industrials",
    "FAST": "Industrials", "WAB": "Industrials", "ROK": "Industrials",
    "LHX": "Industrials", "CARR": "Industrials", "APH": "Industrials",
    "ODFL": "Industrials", "CTAS": "Industrials", "CDW": "Industrials",
    "PPG": "Industrials", "ECL": "Industrials", "VRSK": "Industrials",
    "CPRT": "Industrials", "HAL": "Industrials", "NUE": "Industrials",
    "BA": "Industrials", "LMT": "Industrials", "ETN": "Industrials",
    "ITW": "Industrials", "UPS": "Industrials", "MMM": "Industrials",
    "LIN": "Industrials",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "MPC": "Energy", "OXY": "Energy",
    "FANG": "Energy", "TRGP": "Energy", "WMB": "Energy",
    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities",
    "D": "Utilities", "SRE": "Utilities", "XEL": "Utilities",
    "ED": "Utilities", "AWK": "Utilities",
    "T": "Communication Services", "VZ": "Communication Services",
    "PLD": "Real Estate", "EQIX": "Real Estate", "PSA": "Real Estate",
    "WELL": "Real Estate", "O": "Real Estate", "EXR": "Real Estate",
    "IRM": "Real Estate", "AMT": "Real Estate",
    "SHW": "Materials", "DD": "Materials", "DOW": "Materials",
    "APD": "Materials", "MTD": "Materials",
    "SPY": "Index ETFs", "QQQ": "Index ETFs", "IWM": "Index ETFs",
    "DIA": "Index ETFs",
}


def nan_to_none(v):
    if v is None:
        return None
    try:
        return None if np.isnan(v) else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def aggregate(grp):
    """Compute calibration stats for a group of scored rows."""
    if grp.empty:
        return None
    n = len(grp)
    result = {"n": int(n)}

    # Hit rate at 90%
    if "hit_90" in grp.columns:
        hits = grp["hit_90"].dropna()
        if len(hits) > 0:
            hr = hits.mean()
            result["hit_rate_90"] = nan_to_none(hr)
            result["ece_90"] = nan_to_none(abs(0.90 - hr))
            result["mean_ece"] = result["ece_90"]
            result["hit_rate_90_se"] = nan_to_none(
                np.sqrt(hr * (1 - hr) / len(hits))
            )

    # Brier
    if "brier_score" in grp.columns:
        brier = grp["brier_score"].dropna()
        if len(brier) > 0:
            result["mean_brier"] = nan_to_none(brier.mean())

    # MAD / MEAD / mu
    nad = grp["norm_abs_dev"].dropna()
    nead = grp["norm_expected_abs_dev"].dropna()
    mad = nad.mean() if len(nad) > 0 else float("nan")
    mead = nead.mean() if len(nead) > 0 else float("nan")
    mu = mead / mad if (not np.isnan(mad) and not np.isnan(mead) and mad > 0) else float("nan")

    result["accuracy"] = nan_to_none(mad)
    result["mu"] = nan_to_none(mu)

    if len(nad) > 1:
        result["accuracy_se"] = nan_to_none(nad.std() / np.sqrt(len(nad)))
    else:
        result["accuracy_se"] = None

    if len(nad) > 1 and len(nead) > 1 and not np.isnan(mu) and mad > 0 and mead > 0:
        sd_nad = nad.std()
        sd_nead = nead.std()
        paired = grp[["norm_abs_dev", "norm_expected_abs_dev"]].dropna()
        cov = paired["norm_abs_dev"].cov(paired["norm_expected_abs_dev"]) if len(paired) > 1 else 0.0
        var_ratio = (sd_nad / mad) ** 2 + (sd_nead / mead) ** 2 - 2 * cov / (mad * mead)
        result["mu_se"] = nan_to_none(mu * np.sqrt(var_ratio / n)) if var_ratio > 0 else None
    else:
        result["mu_se"] = None

    result["status"] = "active"
    return result


def main():
    print(f"Reading {STUDY2_SCORED}")
    df = pd.read_csv(STUDY2_SCORED)
    print(f"  {len(df)} rows")

    # Map columns
    df["model_mapped"] = df["model"].map(lambda m: MODEL_MAP.get(m, m))
    df["horizon"] = df["window_days"].map(HORIZON_MAP)
    df["sector"] = df["ticker"].map(SECTOR_MAP).fillna("Other")

    # Compute MAD/MEAD
    df["norm_abs_dev"] = np.abs(df["actual_price"] - df["point_estimate"]) / df["current_price"]
    sigma_implied = (df["ci_90_high"] - df["ci_90_low"]) / (2 * Z_90)
    df["norm_expected_abs_dev"] = (sigma_implied * SQRT_2_OVER_PI) / df["current_price"]

    # Filter valid
    df = df.dropna(subset=["horizon", "actual_price"])
    print(f"  {len(df)} resolved with mapped horizons")

    models = sorted(df["model_mapped"].unique())
    horizons = [h for h in HORIZON_ORDER if h in df["horizon"].unique()]
    tickers = sorted(df["ticker"].unique())

    # Build rolling_index.json
    rolling = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days": None,
        "study_start_date": df["pred_date"].min(),
        "data_through": df["pred_date"].max(),
        "horizons": horizons,
        "models": {},
    }

    for m in models:
        mdf = df[df["model_mapped"] == m]
        model_horizons = {}
        for h in horizons:
            hdf = mdf[mdf["horizon"] == h]
            if hdf.empty:
                continue
            stats = aggregate(hdf)
            if stats is None:
                continue

            # Per-sector breakdown
            sectors = {}
            for sec in sorted(hdf["sector"].unique()):
                sdf = hdf[hdf["sector"] == sec]
                sec_stats = aggregate(sdf)
                if sec_stats:
                    sectors[sec] = sec_stats

            # Per-item breakdown
            items = {}
            for ticker in sorted(hdf["ticker"].unique()):
                tdf = hdf[hdf["ticker"] == ticker]
                item_stats = aggregate(tdf)
                if item_stats:
                    items[ticker] = item_stats

            stats["sectors"] = sectors
            stats["items"] = items
            model_horizons[h] = stats

        rolling["models"][m] = {
            "model_id": m,
            "horizons": model_horizons,
        }

    # Build items_list.json
    items_list = []
    for t in tickers:
        sector = SECTOR_MAP.get(t, "Other")
        items_list.append({"id": t, "label": t, "sector": sector})

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_DIR / "rolling_index.json", "w") as f:
        json.dump(rolling, f)
    print(f"Written -> {OUTPUT_DIR / 'rolling_index.json'}")

    with open(OUTPUT_DIR / "items_list.json", "w") as f:
        json.dump(items_list, f)
    print(f"Written -> {OUTPUT_DIR / 'items_list.json'}")

    # Summary
    for m in models:
        h1 = horizons[0] if horizons else None
        if h1 and h1 in rolling["models"].get(m, {}).get("horizons", {}):
            s = rolling["models"][m]["horizons"][h1]
            print(f"  {m} @ {h1}: n={s['n']}, hit90={s.get('hit_rate_90')}, mu={s.get('mu')}")


if __name__ == "__main__":
    main()
