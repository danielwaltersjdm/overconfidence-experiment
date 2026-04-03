"""
export_data.py — Generate website-ready JSON from scored.csv.

Writes two files to study4/website/data/:
  rolling_index.json  — current rolling 30-day stats per model / domain / horizon
  time_series.json    — daily index values over time (for the website chart)

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

HORIZONS   = ["1d", "1w", "1m"]
HORIZON_DAYS = {"1d": 1, "1w": 7, "1m": 30}
LEVELS     = [50, 80, 90]


def _nan_to_none(v):
    """Replace numpy NaN with None for JSON serialisation."""
    if v is None:
        return None
    try:
        return None if np.isnan(v) else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _aggregate(grp: pd.DataFrame) -> dict:
    """Compute calibration stats for a group of scored rows."""
    if grp.empty:
        return None
    n = len(grp)
    result = {"n": int(n)}
    eces = []
    for level in LEVELS:
        hits = grp[f"hit_{level}"].dropna()
        hr   = hits.mean() if len(hits) > 0 else float("nan")
        ece  = abs(level / 100.0 - hr) if not np.isnan(hr) else float("nan")
        result[f"hit_rate_{level}"] = _nan_to_none(hr)
        result[f"ece_{level}"]      = _nan_to_none(ece)
        if not np.isnan(ece):
            eces.append(ece)
    result["mean_ece"]   = _nan_to_none(np.mean(eces) if eces else float("nan"))
    valid_brier          = grp["brier_score"].dropna()
    result["mean_brier"] = _nan_to_none(valid_brier.mean() if len(valid_brier) > 0 else float("nan"))
    return result


def build_rolling_index(df: pd.DataFrame, config: dict) -> dict:
    """
    Compute rolling 30-day stats per model / domain / horizon.
    Returns the rolling_index.json structure.
    """
    window  = config.get("rolling_window_days", 30)
    today   = datetime.utcnow().date()
    cutoff  = today - timedelta(days=window)
    recent  = df[df["pred_date"] >= cutoff.isoformat()].copy()

    model_ids = {m["name"]: m["model_id"] for m in config["models"]}
    model_names = [m["name"] for m in config["models"]]
    domains  = list(config["domains"].keys())

    study_start = config.get("study", {}).get("start_date")

    out = {
        "generated_at":   datetime.utcnow().isoformat() + "Z",
        "window_days":    window,
        "study_start_date": study_start,
        "data_through":   today.isoformat(),
        "models":         {},
    }

    for model in model_names:
        model_data = {
            "model_id": model_ids.get(model),
            "horizons": {},
        }

        for h_id in HORIZONS:
            h_days = HORIZON_DAYS[h_id]
            # Earliest possible resolution date if study just started
            if study_start:
                first_possible = (
                    datetime.fromisoformat(study_start).date() + timedelta(days=h_days)
                )
                days_until_first = max(0, (first_possible - today).days)
            else:
                days_until_first = None

            grp = recent[
                (recent["model"]   == model) &
                (recent["horizon"] == h_id) &
                (recent["status"]  == "resolved")
            ]

            if grp.empty:
                model_data["horizons"][h_id] = {
                    "status":             "insufficient_data",
                    "days_until_first":   days_until_first,
                }
                continue

            stats = _aggregate(grp)
            stats["status"] = "active"
            stats["days_until_first"] = 0

            # Per-domain breakdown
            domain_breakdown = {}
            for dom in domains:
                d_grp = grp[grp["domain"] == dom]
                domain_breakdown[dom] = _aggregate(d_grp) if not d_grp.empty else None
            stats["domains"] = domain_breakdown

            model_data["horizons"][h_id] = stats

        out["models"][model] = model_data

    return out


def build_time_series(df: pd.DataFrame, config: dict) -> dict:
    """
    Compute daily rolling 30-day 90% hit rate per model per horizon.
    Returns the time_series.json structure.
    """
    window = config.get("rolling_window_days", 30)
    model_names = [m["name"] for m in config["models"]]

    # All unique dates in scored data
    all_dates = sorted(df["pred_date"].dropna().unique())

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days":  window,
        "horizons":     {},
    }

    for h_id in HORIZONS:
        h_df = df[(df["horizon"] == h_id) & (df["status"] == "resolved")]
        if h_df.empty:
            out["horizons"][h_id] = {"status": "insufficient_data"}
            continue

        series_dates   = []
        model_series   = {m: {"hit_rate_90": [], "n": []} for m in model_names}

        for d in all_dates:
            cutoff = (
                datetime.fromisoformat(d).date() - timedelta(days=window)
            ).isoformat()
            window_df = h_df[(h_df["pred_date"] >= cutoff) & (h_df["pred_date"] <= d)]
            if window_df.empty:
                continue

            # Only include dates where at least one model has data
            has_data = any(
                not window_df[window_df["model"] == m].empty
                for m in model_names
            )
            if not has_data:
                continue

            series_dates.append(d)
            for m in model_names:
                m_df = window_df[window_df["model"] == m]
                if m_df.empty:
                    model_series[m]["hit_rate_90"].append(None)
                    model_series[m]["n"].append(0)
                else:
                    hits = m_df["hit_90"].dropna()
                    hr   = _nan_to_none(hits.mean()) if len(hits) > 0 else None
                    model_series[m]["hit_rate_90"].append(hr)
                    model_series[m]["n"].append(int(len(m_df)))

        out["horizons"][h_id] = {
            "status": "active" if series_dates else "insufficient_data",
            "dates":  series_dates,
            "models": model_series,
        }

    return out


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

    # rolling_index.json
    rolling = build_rolling_index(df, config)
    out_path = WEBSITE_DATA / "rolling_index.json"
    out_path.write_text(json.dumps(rolling, indent=2))
    console.print(f"[bold]Written → {out_path}[/bold]")

    # time_series.json
    ts = build_time_series(df, config)
    ts_path = WEBSITE_DATA / "time_series.json"
    ts_path.write_text(json.dumps(ts, indent=2))
    console.print(f"[bold]Written → {ts_path}[/bold]")


if __name__ == "__main__":
    main()
