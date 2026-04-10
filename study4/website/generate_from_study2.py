"""
Generate rolling_index.json and time_series.json for the website dashboard
using real data from Study 2.

Study 2: 100 equities, 9 horizons, 3 models, 5 runs/ticker.
Maps ticker sectors as "domains" and horizon windows as dashboard horizons.

Run from project root:
  python study4/website/generate_from_study2.py
"""

import csv
import json
from collections import defaultdict
from datetime import datetime

SCORED_CSV = "study2/data/results/scored.csv"
OUTPUT_DIR = "study4/website/data"

# Map Study 2 model names to dashboard keys
MODEL_MAP = {
    "claude": "claude",
    "gpt4": "gpt4o",
    "gemini": "gemini",
}

MODEL_IDS = {
    "claude": "claude-sonnet-4-20250514",
    "gpt4o": "gpt-4o",
    "gemini": "gemini-2.5-flash",
}

# Sector groupings for the 100 Study 2 tickers
SECTORS = {
    "Tech": ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
             "ORCL", "MU", "AMD", "QCOM", "TXN", "IBM", "CSCO", "ACN", "CRM",
             "ADBE", "INTU", "NOW", "ANET", "PANW", "CRWD", "MRVL", "PLTR"],
    "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "GS", "MS", "WFC", "AXP",
                   "BLK", "SCHW", "C", "USB", "PNC", "TFC", "SPGI", "MCO",
                   "AON", "ICE", "CME"],
    "Healthcare": ["LLY", "JNJ", "UNH", "ABBV", "MRK", "TMO", "ABT", "AMGN",
                   "ISRG", "GILD", "VRTX", "REGN", "ZTS", "PFE", "SYK", "MDT",
                   "BSX", "ELV", "CI"],
    "Consumer": ["WMT", "COST", "PG", "KO", "PEP", "MCD", "SBUX", "NKE", "HD",
                 "LOW", "TGT", "DIS", "BKNG", "NFLX", "UBER", "PYPL"],
    "Industrial": ["GE", "CAT", "HON", "RTX", "LMT", "DE", "BA", "UPS", "ETN",
                   "MMM", "ITW", "ADI"],
    "Energy": ["XOM", "CVX"],
    "Other": ["T", "VZ", "NEE", "PLD", "AMT", "EQIX"],
}

# Reverse lookup: ticker -> sector
TICKER_SECTOR = {}
for sector, tickers in SECTORS.items():
    for t in tickers:
        TICKER_SECTOR[t] = sector

# Map Study 2 horizons to display labels
# Use 1d, 1w (7d), and 20d as the three dashboard horizons
HORIZON_MAP = {
    1: "1d",
    7: "1w",
    20: "20d",
}

HORIZON_LABELS = {"1d": "1-Day", "1w": "1-Week", "20d": "20-Day"}
ALL_HORIZONS_ORDERED = ["1d", "1w", "20d"]


def load_scored():
    rows = []
    with open(SCORED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            window = int(r["window_days"])
            if window not in HORIZON_MAP:
                continue
            try:
                h50 = int(float(r["hit_50"]))
                h80 = int(float(r["hit_80"]))
                h90 = int(float(r["hit_90"]))
                brier = float(r["brier_score"])
            except (ValueError, KeyError):
                continue
            rows.append({
                "model": MODEL_MAP.get(r["model"], r["model"]),
                "ticker": r["ticker"],
                "pred_date": r["pred_date"],
                "run": int(r["run"]),
                "window_days": window,
                "horizon": HORIZON_MAP[window],
                "sector": TICKER_SECTOR.get(r["ticker"], "Other"),
                "hit_50": h50,
                "hit_80": h80,
                "hit_90": h90,
                "brier": brier,
            })
    return rows


def compute_stats(rows):
    """Compute hit rates and ECE from a list of prediction rows."""
    n = len(rows)
    if n == 0:
        return None
    hr50 = sum(r["hit_50"] for r in rows) / n
    hr80 = sum(r["hit_80"] for r in rows) / n
    hr90 = sum(r["hit_90"] for r in rows) / n
    ece50 = abs(0.50 - hr50)
    ece80 = abs(0.80 - hr80)
    ece90 = abs(0.90 - hr90)
    mean_ece = (ece50 + ece80 + ece90) / 3
    mean_brier = sum(r["brier"] for r in rows) / n
    return {
        "n": n,
        "hit_rate_50": round(hr50, 4),
        "hit_rate_80": round(hr80, 4),
        "hit_rate_90": round(hr90, 4),
        "ece_50": round(ece50, 4),
        "ece_80": round(ece80, 4),
        "ece_90": round(ece90, 4),
        "mean_ece": round(mean_ece, 4),
        "mean_brier": round(mean_brier, 6),
    }


def build_rolling_index(rows):
    """Build rolling_index.json from all Study 2 data (treated as one window)."""
    models = {}
    model_names = sorted(set(r["model"] for r in rows))
    sectors = sorted(SECTORS.keys())

    for m in model_names:
        m_rows = [r for r in rows if r["model"] == m]
        horizons = {}
        for hz in ALL_HORIZONS_ORDERED:
            hz_rows = [r for r in m_rows if r["horizon"] == hz]
            if not hz_rows:
                horizons[hz] = {"status": "insufficient_data", "days_until_first": 0}
                continue
            stats = compute_stats(hz_rows)
            # Domain breakdown by sector
            domains = {}
            for sec in sectors:
                sec_rows = [r for r in hz_rows if r["sector"] == sec]
                if sec_rows:
                    sec_stats = compute_stats(sec_rows)
                    domains[sec.lower()] = {
                        "n": sec_stats["n"],
                        "hit_rate_50": sec_stats["hit_rate_50"],
                        "hit_rate_80": sec_stats["hit_rate_80"],
                        "hit_rate_90": sec_stats["hit_rate_90"],
                    }
            stats["status"] = "active"
            stats["days_until_first"] = 0
            stats["domains"] = domains
            horizons[hz] = stats

        models[m] = {
            "model_id": MODEL_IDS.get(m, m),
            "horizons": horizons,
        }

    dates = sorted(set(r["pred_date"] for r in rows))
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days": 35,
        "study_start_date": dates[0] if dates else "",
        "data_through": dates[-1] if dates else "",
        "source": "Study 2 — Multi-Horizon Equity Predictions",
        "models": models,
    }


def build_time_series(rows):
    """Build time_series.json with per-date hit rates."""
    model_names = sorted(set(r["model"] for r in rows))
    dates = sorted(set(r["pred_date"] for r in rows))

    horizons = {}
    for hz in ALL_HORIZONS_ORDERED:
        hz_rows = [r for r in rows if r["horizon"] == hz]
        if not hz_rows:
            horizons[hz] = {"status": "insufficient_data"}
            continue

        hz_dates = sorted(set(r["pred_date"] for r in hz_rows))
        models_data = {}
        for m in model_names:
            hr90_series = []
            n_series = []
            for d in hz_dates:
                d_rows = [r for r in hz_rows if r["model"] == m and r["pred_date"] == d]
                if d_rows:
                    hr90 = sum(r["hit_90"] for r in d_rows) / len(d_rows)
                    hr90_series.append(round(hr90, 4))
                    n_series.append(len(d_rows))
                else:
                    hr90_series.append(None)
                    n_series.append(0)
            models_data[m] = {
                "hit_rate_90": hr90_series,
                "n": n_series,
            }

        horizons[hz] = {
            "status": "active",
            "dates": hz_dates,
            "models": models_data,
        }

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days": 35,
        "source": "Study 2 — Multi-Horizon Equity Predictions",
        "horizons": horizons,
    }


def main():
    print("Loading Study 2 scored data...")
    rows = load_scored()
    print(f"  {len(rows)} predictions across {len(set(r['model'] for r in rows))} models, "
          f"{len(set(r['horizon'] for r in rows))} horizons")

    print("Building rolling_index.json...")
    ri = build_rolling_index(rows)
    with open(f"{OUTPUT_DIR}/rolling_index.json", "w") as f:
        json.dump(ri, f, indent=2)
    print(f"  Written to {OUTPUT_DIR}/rolling_index.json")

    print("Building time_series.json...")
    ts = build_time_series(rows)
    with open(f"{OUTPUT_DIR}/time_series.json", "w") as f:
        json.dump(ts, f, indent=2)
    print(f"  Written to {OUTPUT_DIR}/time_series.json")

    # Summary
    for m in sorted(ri["models"]):
        h1d = ri["models"][m]["horizons"].get("1d", {})
        if h1d.get("status") == "active":
            print(f"  {m}: 1d hit_rate_90={h1d['hit_rate_90']:.1%}, "
                  f"ECE={h1d['mean_ece']:.1%}, n={h1d['n']}")

    print("Done.")


if __name__ == "__main__":
    main()
