"""
export_data.py — Generate website-ready JSON from scored.csv.

Writes to study4/website/data/:
  rolling_index.json  — current rolling 30-day stats per model / domain / horizon
  time_series.json    — daily index values over time (aggregate + per-sector)
  items_list.json     — ticker/label/sector list for frontend search
  sectors.json        — sector definitions
  items/{TICKER}.json — per-stock time series (loaded on demand by frontend)

Run from study4/ directory after score.py.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from rich.console import Console

console = Console(legacy_windows=False)

BASE_DIR     = Path(__file__).parent
SCORED_FILE  = BASE_DIR / "data" / "results" / "scored.csv"
WEBSITE_DATA = BASE_DIR / "website" / "data"

# Horizons are discovered dynamically from scored.csv.
# Fallback defaults if none found:
DEFAULT_HORIZONS = ["1d", "1w", "1m"]

# Map horizon labels to day counts (for ramp-up calculations)
HORIZON_DAYS = {
    "1d": 1, "2d": 2, "3d": 3, "6d": 6, "7d": 7,
    "14d": 14, "18d": 18, "20d": 20, "21d": 21, "22d": 22, "30d": 30,
    "1w": 7, "1m": 30,
}
LEVELS       = [90]

# ── GICS Sector Mapping ──────────────────────────────────────────────────────

SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "META": "Technology", "AVGO": "Technology",
    "ORCL": "Technology", "AMD": "Technology", "ACN": "Technology",
    "CSCO": "Technology", "ADBE": "Technology", "IBM": "Technology",
    "NOW": "Technology", "INTU": "Technology", "QCOM": "Technology",
    "TXN": "Technology", "CRM": "Technology", "PANW": "Technology",
    "ADI": "Technology", "KLAC": "Technology", "AMAT": "Technology",
    "SNPS": "Technology", "CDNS": "Technology", "MRVL": "Technology",
    "FTNT": "Technology", "IT": "Technology", "KEYS": "Technology",
    "LRCX": "Technology", "MU": "Technology",
    # Financials
    "BRK-B": "Financials", "JPM": "Financials", "V": "Financials",
    "MA": "Financials", "BAC": "Financials", "WFC": "Financials",
    "GS": "Financials", "AXP": "Financials", "BLK": "Financials",
    "SPGI": "Financials", "MS": "Financials", "SCHW": "Financials",
    "C": "Financials", "CB": "Financials", "ADP": "Financials",
    "MMC": "Financials", "CME": "Financials", "ICE": "Financials",
    "FI": "Financials", "USB": "Financials", "PNC": "Financials",
    "AON": "Financials", "AJG": "Financials", "AFL": "Financials",
    "TRV": "Financials", "AIG": "Financials", "BK": "Financials",
    "MSCI": "Financials", "NDAQ": "Financials", "ALL": "Financials",
    "GPN": "Financials",
    # Healthcare
    "LLY": "Healthcare", "UNH": "Healthcare", "JNJ": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare",
    "ABT": "Healthcare", "ISRG": "Healthcare", "AMGN": "Healthcare",
    "ELV": "Healthcare", "BMY": "Healthcare", "VRTX": "Healthcare",
    "GILD": "Healthcare", "REGN": "Healthcare", "BSX": "Healthcare",
    "SYK": "Healthcare", "CI": "Healthcare", "DHR": "Healthcare",
    "MCK": "Healthcare", "HCA": "Healthcare", "ZTS": "Healthcare",
    "DXCM": "Healthcare", "EW": "Healthcare", "BIIB": "Healthcare",
    "IDXX": "Healthcare", "A": "Healthcare", "GEHC": "Healthcare",
    "RMD": "Healthcare", "PFE": "Healthcare", "WST": "Healthcare",
    # Consumer Discretionary
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
    # Consumer Staples
    "PG": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "PM": "Consumer Staples",
    "MDLZ": "Consumer Staples", "CL": "Consumer Staples",
    "MO": "Consumer Staples", "KDP": "Consumer Staples",
    "KR": "Consumer Staples", "HSY": "Consumer Staples",
    "MNST": "Consumer Staples", "GIS": "Consumer Staples",
    "KMB": "Consumer Staples", "STZ": "Consumer Staples",
    # Industrials
    "GE": "Industrials", "CAT": "Industrials", "HON": "Industrials",
    "UNP": "Industrials", "DE": "Industrials", "RTX": "Industrials",
    "LIN": "Industrials", "FDX": "Industrials", "NSC": "Industrials",
    "PCAR": "Industrials", "GD": "Industrials", "EMR": "Industrials",
    "JCI": "Industrials", "FAST": "Industrials", "WAB": "Industrials",
    "ROK": "Industrials", "LHX": "Industrials", "CARR": "Industrials",
    "APH": "Industrials", "ODFL": "Industrials", "CTAS": "Industrials",
    "CDW": "Industrials", "PPG": "Industrials", "ECL": "Industrials",
    "VRSK": "Industrials", "CPRT": "Industrials", "HAL": "Industrials",
    "NUE": "Industrials",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "SLB": "Energy", "MPC": "Energy", "OXY": "Energy",
    "FANG": "Energy", "HES": "Energy", "TRGP": "Energy",
    "WMB": "Energy",
    # Utilities
    "NEE": "Utilities", "SO": "Utilities", "DUK": "Utilities",
    "D": "Utilities", "SRE": "Utilities", "XEL": "Utilities",
    "ED": "Utilities", "AWK": "Utilities",
    # Communication Services
    "T": "Communication Services", "VZ": "Communication Services",
    # Real Estate
    "PLD": "Real Estate", "EQIX": "Real Estate", "PSA": "Real Estate",
    "WELL": "Real Estate", "O": "Real Estate", "EXR": "Real Estate",
    "IRM": "Real Estate",
    # Materials
    "SHW": "Materials", "DD": "Materials", "DOW": "Materials",
    "APD": "Materials", "MTD": "Materials",
    # Index ETFs
    "SPY": "Index ETFs", "QQQ": "Index ETFs", "IWM": "Index ETFs",
    "DIA": "Index ETFs",
    # Remaining — mapped individually
    "ON": "Technology", "PYPL": "Financials",
    # Study 2 tickers not in Study 4's 200
    "NKE": "Consumer Discretionary", "DIS": "Communication Services",
    "UBER": "Technology", "PLTR": "Technology",
    "LMT": "Industrials", "BA": "Industrials", "UPS": "Industrials",
    "ETN": "Industrials", "MMM": "Industrials", "ITW": "Industrials",
    "ANET": "Technology", "CRWD": "Technology",
    "MCO": "Financials", "AMT": "Real Estate",
    "MDT": "Healthcare", "TFC": "Financials",
}


def _nan_to_none(v):
    """Replace numpy NaN with None for JSON serialisation."""
    if v is None:
        return None
    try:
        return None if np.isnan(v) else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _aggregate(grp: pd.DataFrame) -> dict | None:
    """Compute calibration stats for a group of scored rows."""
    if grp.empty:
        return None
    n = len(grp)
    result = {"n": int(n)}
    eces = []
    for level in LEVELS:
        col = f"hit_{level}"
        if col not in grp.columns:
            continue
        hits = grp[col].dropna()
        hr   = hits.mean() if len(hits) > 0 else float("nan")
        ece  = abs(level / 100.0 - hr) if not np.isnan(hr) else float("nan")
        result[f"hit_rate_{level}"] = _nan_to_none(hr)
        result[f"ece_{level}"]      = _nan_to_none(ece)
        if not np.isnan(ece):
            eces.append(ece)
    result["mean_ece"]   = _nan_to_none(np.mean(eces) if eces else float("nan"))
    valid_brier          = grp["brier_score"].dropna() if "brier_score" in grp.columns else pd.Series(dtype=float)
    result["mean_brier"] = _nan_to_none(valid_brier.mean() if len(valid_brier) > 0 else float("nan"))

    # Soll & Klayman (2004) metrics
    valid_nad  = grp["norm_abs_dev"].dropna() if "norm_abs_dev" in grp.columns else pd.Series(dtype=float)
    valid_nead = grp["norm_expected_abs_dev"].dropna() if "norm_expected_abs_dev" in grp.columns else pd.Series(dtype=float)
    mad  = valid_nad.mean()  if len(valid_nad)  > 0 else float("nan")
    mead = valid_nead.mean() if len(valid_nead) > 0 else float("nan")
    result["accuracy"] = _nan_to_none(mad)
    result["mu"]       = _nan_to_none(mead / mad if (not np.isnan(mad) and not np.isnan(mead) and mad > 0) else float("nan"))
    return result


def _compute_series_point(m_df: pd.DataFrame) -> dict:
    """Compute a single time-series data point for one model on one date window."""
    if m_df.empty:
        return {"hit_rate_90": None, "mu": None, "accuracy": None, "n": 0}
    hits = m_df["hit_90"].dropna() if "hit_90" in m_df.columns else pd.Series(dtype=float)
    hr   = _nan_to_none(hits.mean()) if len(hits) > 0 else None

    valid_nad  = m_df["norm_abs_dev"].dropna() if "norm_abs_dev" in m_df.columns else pd.Series(dtype=float)
    valid_nead = m_df["norm_expected_abs_dev"].dropna() if "norm_expected_abs_dev" in m_df.columns else pd.Series(dtype=float)
    mad  = valid_nad.mean()  if len(valid_nad)  > 0 else float("nan")
    mead = valid_nead.mean() if len(valid_nead) > 0 else float("nan")
    mu   = mead / mad if (not np.isnan(mad) and not np.isnan(mead) and mad > 0) else float("nan")

    return {
        "hit_rate_90": hr,
        "mu":          _nan_to_none(mu),
        "accuracy":    _nan_to_none(mad),
        "n":           int(len(m_df)),
    }


def _sort_horizons(horizons: list[str]) -> list[str]:
    """Sort horizon labels by day count (e.g., '1d', '2d', ..., '30d')."""
    def _days(h):
        return HORIZON_DAYS.get(h, int(h.replace("d", "").replace("w", "").replace("m", "")))
    return sorted(horizons, key=_days)


def _discover_horizons(df: pd.DataFrame) -> list[str]:
    """Get sorted unique horizon labels from the data."""
    horizons = df["horizon"].dropna().unique().tolist()
    return _sort_horizons(horizons) if horizons else DEFAULT_HORIZONS


def build_rolling_index(df: pd.DataFrame, config: dict, horizons: list[str]) -> dict:
    """Rolling 30-day stats per model / horizon, with sector + item breakdowns."""
    window  = config.get("rolling_window_days", 30)
    today   = datetime.utcnow().date()
    cutoff  = today - timedelta(days=window)
    recent  = df[df["pred_date"] >= cutoff.isoformat()].copy()

    model_ids   = {m["name"]: m["model_id"] for m in config["models"]}
    model_names = [m["name"] for m in config["models"]]
    study_start = config.get("study", {}).get("start_date")

    # Add sector column
    recent["sector"] = recent["item_id"].map(SECTOR_MAP).fillna("Other")

    out = {
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "window_days":      window,
        "study_start_date": study_start,
        "data_through":     today.isoformat(),
        "horizons_list":    horizons,
        "models":           {},
    }

    for model in model_names:
        model_data = {"model_id": model_ids.get(model), "horizons": {}}

        for h_id in horizons:
            h_days = HORIZON_DAYS.get(h_id, 1)
            if study_start:
                first_possible = datetime.fromisoformat(study_start).date() + timedelta(days=h_days)
                days_until_first = max(0, (first_possible - today).days)
            else:
                days_until_first = None

            grp = recent[
                (recent["model"] == model) &
                (recent["horizon"] == h_id) &
                (recent["status"] == "resolved")
            ]

            if grp.empty:
                model_data["horizons"][h_id] = {
                    "status": "insufficient_data",
                    "days_until_first": days_until_first,
                }
                continue

            stats = _aggregate(grp)
            stats["status"] = "active"
            stats["days_until_first"] = 0

            # Per-sector breakdown
            sector_breakdown = {}
            for sec in sorted(grp["sector"].unique()):
                s_grp = grp[grp["sector"] == sec]
                sector_breakdown[sec] = _aggregate(s_grp)
            stats["sectors"] = sector_breakdown

            # Per-item breakdown
            item_breakdown = {}
            for item_id in sorted(grp["item_id"].unique()):
                i_grp = grp[grp["item_id"] == item_id]
                item_breakdown[item_id] = _aggregate(i_grp)
            stats["items"] = item_breakdown

            model_data["horizons"][h_id] = stats

        out["models"][model] = model_data

    return out


def build_time_series(df: pd.DataFrame, config: dict, horizons: list[str]) -> dict:
    """Daily rolling 30-day metrics per model per horizon, aggregate + per-sector."""
    window      = config.get("rolling_window_days", 30)
    model_names = [m["name"] for m in config["models"]]
    all_dates   = sorted(df["pred_date"].dropna().unique())

    df["sector"] = df["item_id"].map(SECTOR_MAP).fillna("Other")
    all_sectors  = sorted(df["sector"].unique())

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days":  window,
        "horizons":     {},
    }

    for h_id in horizons:
        h_df = df[(df["horizon"] == h_id) & (df["status"] == "resolved")]
        if h_df.empty:
            out["horizons"][h_id] = {"status": "insufficient_data"}
            continue

        series_dates = []
        model_series = {m: {"hit_rate_90": [], "mu": [], "accuracy": [], "n": []} for m in model_names}
        # Per-sector series
        sector_series = {}
        for sec in all_sectors:
            sector_series[sec] = {
                "models": {m: {"hit_rate_90": [], "mu": [], "accuracy": [], "n": []} for m in model_names}
            }

        for d in all_dates:
            cutoff = (datetime.fromisoformat(d).date() - timedelta(days=window)).isoformat()
            window_df = h_df[(h_df["pred_date"] >= cutoff) & (h_df["pred_date"] <= d)]
            if window_df.empty:
                continue

            has_data = any(not window_df[window_df["model"] == m].empty for m in model_names)
            if not has_data:
                continue

            series_dates.append(d)
            for m in model_names:
                m_df = window_df[window_df["model"] == m]
                pt = _compute_series_point(m_df)
                for k in ("hit_rate_90", "mu", "accuracy"):
                    model_series[m][k].append(pt[k])
                model_series[m]["n"].append(pt["n"])

                # Per-sector
                for sec in all_sectors:
                    sm_df = m_df[m_df["sector"] == sec]
                    spt = _compute_series_point(sm_df)
                    for k in ("hit_rate_90", "mu", "accuracy"):
                        sector_series[sec]["models"][m][k].append(spt[k])
                    sector_series[sec]["models"][m]["n"].append(spt["n"])

        out["horizons"][h_id] = {
            "status":  "active" if series_dates else "insufficient_data",
            "dates":   series_dates,
            "models":  model_series,
            "sectors": sector_series,
        }

    return out


def build_item_series(df: pd.DataFrame, config: dict, items_meta: list[dict], horizons: list[str]):
    """Write per-ticker time series JSON files to website/data/items/."""
    window      = config.get("rolling_window_days", 30)
    model_names = [m["name"] for m in config["models"]]
    items_dir   = WEBSITE_DATA / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    all_dates = sorted(df["pred_date"].dropna().unique())
    item_lookup = {it["id"]: it for it in items_meta}

    written = 0
    for item_id in df["item_id"].unique():
        meta = item_lookup.get(item_id, {"id": item_id, "label": item_id, "sector": SECTOR_MAP.get(item_id, "Other")})
        item_out = {
            "ticker": item_id,
            "label":  meta.get("label", item_id),
            "sector": SECTOR_MAP.get(item_id, "Other"),
            "horizons": {},
        }

        i_df = df[df["item_id"] == item_id]

        for h_id in horizons:
            h_df = i_df[(i_df["horizon"] == h_id) & (i_df["status"] == "resolved")]
            if h_df.empty:
                item_out["horizons"][h_id] = {"status": "insufficient_data"}
                continue

            series_dates = []
            model_series = {m: {"hit_rate_90": [], "mu": [], "accuracy": [], "n": []} for m in model_names}

            for d in all_dates:
                cutoff = (datetime.fromisoformat(d).date() - timedelta(days=window)).isoformat()
                window_df = h_df[(h_df["pred_date"] >= cutoff) & (h_df["pred_date"] <= d)]
                if window_df.empty:
                    continue

                has_data = any(not window_df[window_df["model"] == m].empty for m in model_names)
                if not has_data:
                    continue

                series_dates.append(d)
                for m in model_names:
                    m_df = window_df[window_df["model"] == m]
                    pt = _compute_series_point(m_df)
                    for k in ("hit_rate_90", "mu", "accuracy"):
                        model_series[m][k].append(pt[k])
                    model_series[m]["n"].append(pt["n"])

            item_out["horizons"][h_id] = {
                "status": "active" if series_dates else "insufficient_data",
                "dates":  series_dates,
                "models": model_series,
            }

        out_path = items_dir / f"{item_id}.json"
        out_path.write_text(json.dumps(item_out, indent=1))
        written += 1

    console.print(f"[bold]Written → {items_dir}/[/bold] ({written} item files)")


def build_items_list(config: dict, df: pd.DataFrame = None) -> list[dict]:
    """Build items_list.json from config + scored data, adding sector info."""
    items = []
    seen = set()
    # From config
    for domain_name, domain_cfg in config.get("domains", {}).items():
        for item in domain_cfg.get("items", []):
            item_id = item["id"]
            if item_id not in seen:
                items.append({
                    "id":     item_id,
                    "label":  item.get("label", item_id),
                    "sector": SECTOR_MAP.get(item_id, "Other"),
                })
                seen.add(item_id)
    # From data (covers tickers not in config, e.g. Study 2 backfill)
    if df is not None:
        for item_id in sorted(df["item_id"].unique()):
            if item_id not in seen:
                items.append({
                    "id":     item_id,
                    "label":  item_id,
                    "sector": SECTOR_MAP.get(item_id, "Other"),
                })
                seen.add(item_id)
    return items


def main():
    if not SCORED_FILE.exists():
        console.print(f"[red]scored.csv not found: {SCORED_FILE}. Run score.py first.[/red]")
        return

    df = pd.read_csv(SCORED_FILE)
    if df.empty:
        console.print("[yellow]scored.csv is empty — nothing to export.[/yellow]")
        return

    with open(BASE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)

    WEBSITE_DATA.mkdir(parents=True, exist_ok=True)

    # Discover horizons from data
    horizons = _discover_horizons(df)
    console.print(f"[bold]Horizons discovered:[/bold] {horizons}")

    # items_list.json + sectors.json
    items_meta = build_items_list(config, df)
    items_path = WEBSITE_DATA / "items_list.json"
    items_path.write_text(json.dumps(items_meta, indent=1))
    console.print(f"[bold]Written → {items_path}[/bold] ({len(items_meta)} items)")

    sectors = sorted(set(SECTOR_MAP.values()))
    sectors_path = WEBSITE_DATA / "sectors.json"
    sectors_path.write_text(json.dumps(sectors, indent=1))
    console.print(f"[bold]Written → {sectors_path}[/bold]")

    # rolling_index.json
    rolling = build_rolling_index(df, config, horizons)
    out_path = WEBSITE_DATA / "rolling_index.json"
    out_path.write_text(json.dumps(rolling, indent=2))
    console.print(f"[bold]Written → {out_path}[/bold]")

    # time_series.json (aggregate + per-sector)
    ts = build_time_series(df, config, horizons)
    ts_path = WEBSITE_DATA / "time_series.json"
    ts_path.write_text(json.dumps(ts, indent=2))
    console.print(f"[bold]Written → {ts_path}[/bold]")

    # Per-item time series
    build_item_series(df, config, items_meta, horizons)


if __name__ == "__main__":
    main()
