"""
fetch_actuals.py — Study 4 actuals fetching.

Scans data/predictions/ for all JSON files. For each prediction × horizon whose
target_date has elapsed, fetches the actual outcome and writes a row to
data/actuals/actuals.csv. Idempotent: already-resolved rows are skipped.

Run from study4/ directory.
Usage:
  python fetch_actuals.py [--date YYYY-MM-DD]
"""

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml
from rich.console import Console

Console_obj = Console(legacy_windows=False)
console = Console_obj

BASE_DIR     = Path(__file__).parent
PRED_DIR     = BASE_DIR / "data" / "predictions"
ACTUALS_DIR  = BASE_DIR / "data" / "actuals"
ACTUALS_FILE = ACTUALS_DIR / "actuals.csv"

ACTUALS_COLUMNS = [
    "model", "domain", "item", "pred_date", "horizon", "horizon_days",
    "target_date", "adjusted_target_date", "unit", "current_value",
    "point_estimate",
    "ci_50_low", "ci_50_high",
    "ci_80_low", "ci_80_high",
    "ci_90_low", "ci_90_high",
    "actual_value", "adjustment_note",
    "status", "fetched_at",
]

HORIZON_DAYS = {"1d": 1, "1w": 7, "1m": 30}


# ── Trading day helpers ────────────────────────────────────────────────────────

def next_trading_day(d: date) -> tuple[date, str]:
    """
    Return (adjusted_date, note) where adjusted_date is d if it's a weekday,
    otherwise the next Monday. Does not account for public holidays.
    """
    if d.weekday() < 5:
        return d, ""
    days_ahead = 7 - d.weekday()  # Saturday→2, Sunday→1
    adjusted = d + timedelta(days=days_ahead)
    return adjusted, f"original {d.isoformat()} was weekend; adjusted to {adjusted.isoformat()}"


# ── Actuals fetchers ───────────────────────────────────────────────────────────

def fetch_stock_price(yf_ticker: str, target: date) -> tuple[float, date, str]:
    """
    Return (price, actual_date, adjustment_note).
    Uses yfinance. Takes the first available close on or after target_date.
    """
    import yfinance as yf

    adjusted, note = next_trading_day(target)
    end = adjusted + timedelta(days=7)  # buffer for holidays
    df = yf.download(
        yf_ticker, start=adjusted.isoformat(), end=end.isoformat(),
        auto_adjust=True, progress=False, actions=False,
    )
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {yf_ticker} from {adjusted}")
    actual_date = df.index[0].date()
    price = float(df["Close"].iloc[0])
    if actual_date != adjusted:
        note = f"original {adjusted.isoformat()} unavailable; used {actual_date.isoformat()}"
    return price, actual_date, note


def fetch_crypto_price(coingecko_id: str, target: date,
                       retries: int = 3) -> tuple[float, date, str]:
    """CoinGecko historical price endpoint. Crypto trades 24/7."""
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/history"
    params = {"date": target.strftime("%d-%m-%Y"), "localization": "false"}
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            price = float(data["market_data"]["current_price"]["usd"])
            return price, target, ""
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(5 * (2 ** attempt))
            else:
                raise RuntimeError(f"CoinGecko failed for {coingecko_id} on {target}: {e}")


def fetch_forex_rate(yf_ticker: str, target: date) -> tuple[float, date, str]:
    """Forex via yfinance. Same logic as stocks."""
    return fetch_stock_price(yf_ticker, target)


def fetch_weather_temp(lat: float, lon: float, target: date) -> tuple[float, date, str]:
    """Daily mean temperature (°F) from Open-Meteo archive."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":         lat,
        "longitude":        lon,
        "start_date":       target.isoformat(),
        "end_date":         target.isoformat(),
        "daily":            "temperature_2m_mean",
        "temperature_unit": "fahrenheit",
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    val = data["daily"]["temperature_2m_mean"][0]
    if val is None:
        raise RuntimeError(f"Open-Meteo returned null for {lat},{lon} on {target}")
    return float(val), target, ""


# ── Item lookup helpers ────────────────────────────────────────────────────────

def build_item_lookup(config: dict) -> dict:
    """Return {(domain, item_id): item_cfg} for quick lookup."""
    lookup = {}
    for domain, dcfg in config["domains"].items():
        for item in dcfg.get("items", []):
            lookup[(domain, item["id"])] = (item, dcfg)
    return lookup


def fetch_actual(domain: str, item_cfg: dict, domain_cfg: dict,
                 target: date) -> tuple[float, date, str]:
    """Dispatch to the correct source."""
    if domain == "stocks":
        return fetch_stock_price(item_cfg["yfinance_ticker"], target)
    if domain == "crypto":
        return fetch_crypto_price(item_cfg["coingecko_id"], target)
    if domain == "forex":
        return fetch_forex_rate(item_cfg["yfinance_ticker"], target)
    if domain == "weather":
        return fetch_weather_temp(item_cfg["lat"], item_cfg["lon"], target)
    raise ValueError(f"Unknown domain: {domain}")


# ── CSV helpers ────────────────────────────────────────────────────────────────

def load_actuals() -> pd.DataFrame:
    if ACTUALS_FILE.exists():
        return pd.read_csv(ACTUALS_FILE, dtype=str)
    return pd.DataFrame(columns=ACTUALS_COLUMNS)


def is_resolved(actuals_df: pd.DataFrame, model: str, domain: str,
                item: str, pred_date: str, horizon: str) -> bool:
    if actuals_df.empty:
        return False
    mask = (
        (actuals_df["model"]     == model) &
        (actuals_df["domain"]    == domain) &
        (actuals_df["item"]      == item) &
        (actuals_df["pred_date"] == pred_date) &
        (actuals_df["horizon"]   == horizon) &
        (actuals_df["status"]    == "resolved")
    )
    return mask.any()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch Study 4 actuals")
    parser.add_argument("--date", help="Treat this as 'today' for elapsed-horizon checks (YYYY-MM-DD)")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()

    with open(BASE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)

    item_lookup = build_item_lookup(config)
    ACTUALS_DIR.mkdir(parents=True, exist_ok=True)

    actuals_df = load_actuals()
    new_rows   = []

    pred_files = sorted(PRED_DIR.glob("*.json"))
    console.print(f"\n[bold]Fetch actuals — {today}[/bold] ({len(pred_files)} prediction files)")

    for pred_path in pred_files:
        try:
            record = json.loads(pred_path.read_text())
        except Exception as e:
            console.print(f"  [red]Cannot read {pred_path.name}: {e}[/red]")
            continue

        if record.get("status") != "collected":
            continue

        model     = record["model"]
        domain    = record["domain"]
        item      = record["item"]
        pred_date = record["pred_date"]
        unit      = record.get("unit", "")
        ref_val   = record.get("current_value")
        horizons  = record.get("horizons", {})

        key = (domain, item)
        if key not in item_lookup:
            console.print(f"  [yellow]Unknown item {domain}/{item}; skipping[/yellow]")
            continue
        item_cfg, domain_cfg = item_lookup[key]

        for h_id, h_days in HORIZON_DAYS.items():
            target_date = date.fromisoformat(pred_date) + timedelta(days=h_days)
            if today < target_date:
                continue  # horizon not yet elapsed

            if is_resolved(actuals_df, model, domain, item, pred_date, h_id):
                continue  # already have this actual

            # Extract CI bounds from stored prediction
            h_data = horizons.get(h_id, {})
            pe = h_data.get("point_estimate")
            ci50 = h_data.get("50_ci", [None, None])
            ci80 = h_data.get("80_ci", [None, None])
            ci90 = h_data.get("90_ci", [None, None])

            actual_val  = None
            adj_date    = target_date
            adj_note    = ""
            row_status  = "failed"
            fetched_at  = datetime.utcnow().isoformat() + "Z"

            try:
                actual_val, adj_date, adj_note = fetch_actual(
                    domain, item_cfg, domain_cfg, target_date
                )
                row_status = "resolved"
                console.print(
                    f"  [green]OK[/green] {model}/{domain}/{item}/{pred_date}/{h_id}"
                    f" → {actual_val}"
                )
            except Exception as e:
                row_status = "failed"
                adj_note   = str(e)
                console.print(
                    f"  [red]FAIL[/red] {model}/{domain}/{item}/{pred_date}/{h_id}: {e}"
                )
                # Rate-limit pause on CoinGecko failures
                if domain == "crypto":
                    time.sleep(5)

            new_rows.append({
                "model":               model,
                "domain":              domain,
                "item":                item,
                "pred_date":           pred_date,
                "horizon":             h_id,
                "horizon_days":        h_days,
                "target_date":         target_date.isoformat(),
                "adjusted_target_date": adj_date.isoformat() if adj_date else "",
                "unit":                unit,
                "current_value":       ref_val,
                "point_estimate":      pe,
                "ci_50_low":           ci50[0] if ci50 else None,
                "ci_50_high":          ci50[1] if ci50 else None,
                "ci_80_low":           ci80[0] if ci80 else None,
                "ci_80_high":          ci80[1] if ci80 else None,
                "ci_90_low":           ci90[0] if ci90 else None,
                "ci_90_high":          ci90[1] if ci90 else None,
                "actual_value":        actual_val,
                "adjustment_note":     adj_note,
                "status":              row_status,
                "fetched_at":          fetched_at,
            })

            # CoinGecko rate limit: pause between crypto calls
            if domain == "crypto":
                time.sleep(3)

    if new_rows:
        new_df  = pd.DataFrame(new_rows, columns=ACTUALS_COLUMNS)
        combined = pd.concat([actuals_df, new_df], ignore_index=True)
        combined.to_csv(ACTUALS_FILE, index=False)
        console.print(f"\n[bold]Added {len(new_rows)} rows → {ACTUALS_FILE}[/bold]")
    else:
        console.print("\n[dim]No new actuals to fetch.[/dim]")


if __name__ == "__main__":
    main()
