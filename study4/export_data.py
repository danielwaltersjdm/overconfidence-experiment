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

HORIZONS     = ["1d", "1w", "1m"]
HORIZON_DAYS = {"1d": 1, "1w": 7, "1m": 30}
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
    "NXPI": "Technology", "FICO": "Financials",
    # Study 2 extra tickers not in Study 4 config
    "BA": "Industrials", "LMT": "Industrials", "ETN": "Industrials",
    "ITW": "Industrials", "UPS": "Industrials", "MMM": "Industrials",
    "AMT": "Real Estate", "ANET": "Technology", "CRWD": "Technology",
    "DIS": "Communication Services", "MCO": "Financials", "MDT": "Healthcare",
    "NKE": "Consumer Discretionary", "PLTR": "Technology", "TFC": "Financials",
    "UBER": "Consumer Discretionary", "CTSH": "Technology",
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
    mu   = mead / mad if (not np.isnan(mad) and not np.isnan(mead) and mad > 0) else float("nan")
    result["accuracy"] = _nan_to_none(mad)
    result["mu"]       = _nan_to_none(mu)

    # Standard errors for error bars
    # Accuracy SE: std(norm_abs_dev) / sqrt(n)
    if len(valid_nad) > 1:
        result["accuracy_se"] = _nan_to_none(valid_nad.std() / np.sqrt(len(valid_nad)))
    else:
        result["accuracy_se"] = None

    # Mu SE via delta method: mu * sqrt((sd_nad/mad)^2 + (sd_nead/mead)^2 - 2*cov/(mad*mead)) / sqrt(n)
    if len(valid_nad) > 1 and len(valid_nead) > 1 and not np.isnan(mu) and mad > 0 and mead > 0:
        sd_nad  = valid_nad.std()
        sd_nead = valid_nead.std()
        # Use paired observations for covariance
        paired = grp[["norm_abs_dev", "norm_expected_abs_dev"]].dropna()
        if len(paired) > 1:
            cov = paired["norm_abs_dev"].cov(paired["norm_expected_abs_dev"])
        else:
            cov = 0.0
        var_ratio = (sd_nad / mad) ** 2 + (sd_nead / mead) ** 2 - 2 * cov / (mad * mead)
        if var_ratio > 0:
            result["mu_se"] = _nan_to_none(mu * np.sqrt(var_ratio / n))
        else:
            result["mu_se"] = None
    else:
        result["mu_se"] = None

    # Hit rate SE: binomial SE = sqrt(p(1-p)/n)
    for level in LEVELS:
        col = f"hit_{level}"
        if col in grp.columns:
            hits = grp[col].dropna()
            if len(hits) > 0:
                p = hits.mean()
                result[f"hit_rate_{level}_se"] = _nan_to_none(np.sqrt(p * (1 - p) / len(hits)))

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

    # Standard errors
    hr_se = _nan_to_none(np.sqrt(hr * (1 - hr) / len(hits))) if (hr is not None and len(hits) > 0) else None
    acc_se = _nan_to_none(valid_nad.std() / np.sqrt(len(valid_nad))) if len(valid_nad) > 1 else None
    mu_se = None
    if len(valid_nad) > 1 and len(valid_nead) > 1 and not np.isnan(mu) and mad > 0 and mead > 0:
        paired = m_df[["norm_abs_dev", "norm_expected_abs_dev"]].dropna()
        if len(paired) > 1:
            cov = paired["norm_abs_dev"].cov(paired["norm_expected_abs_dev"])
            var_ratio = (valid_nad.std() / mad) ** 2 + (valid_nead.std() / mead) ** 2 - 2 * cov / (mad * mead)
            if var_ratio > 0:
                mu_se = _nan_to_none(mu * np.sqrt(var_ratio / len(m_df)))

    return {
        "hit_rate_90": hr,
        "mu":          _nan_to_none(mu),
        "accuracy":    _nan_to_none(mad),
        "n":           int(len(m_df)),
        "hit_rate_90_se": hr_se,
        "mu_se":       mu_se,
        "accuracy_se": acc_se,
    }


def _sort_horizons(horizons: list[str]) -> list[str]:
    """Sort horizon labels by their numeric day value."""
    def _h_days(h: str) -> int:
        h = h.lower().strip()
        if h.endswith("d"):
            return int(h[:-1])
        elif h.endswith("w"):
            return int(h[:-1]) * 7
        elif h.endswith("m"):
            return int(h[:-1]) * 30
        return 9999
    return sorted(horizons, key=_h_days)


def build_rolling_index(df: pd.DataFrame, config: dict) -> dict:
    """Rolling 30-day stats per model / horizon, with sector + item breakdowns."""
    window  = config.get("rolling_window_days", 30)

    # Use max date from actual data, not system clock
    max_date = df["pred_date"].dropna().max()
    today = datetime.fromisoformat(max_date).date() if max_date else datetime.utcnow().date()
    cutoff  = today - timedelta(days=window)
    recent  = df[df["pred_date"] >= cutoff.isoformat()].copy()

    # Discover models from data (not just config)
    model_ids   = {m["name"]: m["model_id"] for m in config["models"]}
    data_models = sorted(df["model"].dropna().unique())
    model_names = list(dict.fromkeys(data_models))  # deduplicated, data order
    study_start = config.get("study", {}).get("start_date")

    # Discover horizons from data
    data_horizons = _sort_horizons(list(df["horizon"].dropna().unique()))

    # Add sector column
    recent["sector"] = recent["item_id"].map(SECTOR_MAP).fillna("Other")

    out = {
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "window_days":      window,
        "study_start_date": study_start,
        "data_through":     today.isoformat(),
        "horizons":         data_horizons,
        "models":           {},
    }

    for model in model_names:
        model_data = {"model_id": model_ids.get(model), "horizons": {}}

        for h_id in data_horizons:
            grp = recent[
                (recent["model"] == model) &
                (recent["horizon"] == h_id) &
                (recent["status"] == "resolved")
            ]

            if grp.empty:
                model_data["horizons"][h_id] = {
                    "status": "insufficient_data",
                }
                continue

            stats = _aggregate(grp)
            stats["status"] = "active"

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


def build_time_series(df: pd.DataFrame, config: dict) -> dict:
    """Daily rolling 30-day metrics per model per horizon, aggregate + per-sector."""
    window      = config.get("rolling_window_days", 30)
    # Discover models from data
    model_names = sorted(df["model"].dropna().unique())
    all_dates   = sorted(df["pred_date"].dropna().unique())

    df["sector"] = df["item_id"].map(SECTOR_MAP).fillna("Other")
    all_sectors  = sorted(df["sector"].unique())

    # Discover horizons from data
    data_horizons = _sort_horizons(list(df["horizon"].dropna().unique()))

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days":  window,
        "horizons":     {},
    }

    for h_id in data_horizons:
        h_df = df[(df["horizon"] == h_id) & (df["status"] == "resolved")]
        if h_df.empty:
            out["horizons"][h_id] = {"status": "insufficient_data"}
            continue

        series_dates = []
        model_series = {m: {"hit_rate_90": [], "mu": [], "accuracy": [], "n": [],
                            "hit_rate_90_se": [], "mu_se": [], "accuracy_se": []} for m in model_names}
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
                for k in ("hit_rate_90", "mu", "accuracy", "hit_rate_90_se", "mu_se", "accuracy_se"):
                    model_series[m][k].append(pt.get(k))
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


def build_item_series(df: pd.DataFrame, config: dict, items_meta: list[dict]):
    """Write per-ticker time series JSON files to website/data/items/."""
    window      = config.get("rolling_window_days", 30)
    # Discover models from data
    model_names = sorted(df["model"].dropna().unique())
    # Discover horizons from data
    data_horizons = _sort_horizons(list(df["horizon"].dropna().unique()))

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

        for h_id in data_horizons:
            h_df = i_df[(i_df["horizon"] == h_id) & (i_df["status"] == "resolved")]
            if h_df.empty:
                item_out["horizons"][h_id] = {"status": "insufficient_data"}
                continue

            series_dates = []
            model_series = {m: {"hit_rate_90": [], "mu": [], "accuracy": [], "n": [],
                            "hit_rate_90_se": [], "mu_se": [], "accuracy_se": []} for m in model_names}

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
    seen = set()
    items = []
    # First add items from config (has labels)
    for domain_name, domain_cfg in config.get("domains", {}).items():
        for item in domain_cfg.get("items", []):
            item_id = item["id"]
            if item_id not in seen:
                seen.add(item_id)
                items.append({
                    "id":     item_id,
                    "label":  item.get("label", item_id),
                    "sector": SECTOR_MAP.get(item_id, "Other"),
                })
    # Then add any items from scored data not in config
    if df is not None:
        for item_id in sorted(df["item_id"].dropna().unique()):
            if item_id not in seen:
                seen.add(item_id)
                items.append({
                    "id":     item_id,
                    "label":  item_id,
                    "sector": SECTOR_MAP.get(item_id, "Other"),
                })
    return items


def main():
    if not SCORED_FILE.exists():
        console.print(f"[red]scored.csv not found: {SCORED_FILE}. Run score.py first.[/red]")
        return

    df = pd.read_csv(SCORED_FILE)
    if df.empty:
        console.print("[yellow]scored.csv is empty — nothing to export.[/yellow]")
        return

    # Normalize column names: Study 4 native uses "item", convert_study2 uses "item_id"
    if "item" in df.columns and "item_id" not in df.columns:
        df = df.rename(columns={"item": "item_id"})
    # Study 4 native uses "current_value", convert_study2 already maps to "current_value"
    console.print(f"[bold]Loaded scored.csv:[/bold] {len(df)} rows, "
                  f"models={sorted(df['model'].unique())}, "
                  f"horizons={sorted(df['horizon'].unique())}")

    with open(BASE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)

    WEBSITE_DATA.mkdir(parents=True, exist_ok=True)

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
    rolling = build_rolling_index(df, config)
    out_path = WEBSITE_DATA / "rolling_index.json"
    out_path.write_text(json.dumps(rolling, indent=2))
    console.print(f"[bold]Written → {out_path}[/bold]")

    # time_series.json (aggregate + per-sector)
    ts = build_time_series(df, config)
    ts_path = WEBSITE_DATA / "time_series.json"
    ts_path.write_text(json.dumps(ts, indent=2))
    console.print(f"[bold]Written → {ts_path}[/bold]")

    # Per-item time series
    build_item_series(df, config, items_meta)


if __name__ == "__main__":
    main()
