"""
Fetch actual stock prices after the prediction window closes.
Matches predictions in data/predictions/ to their actual outcomes via yfinance.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
import yaml
from rich.console import Console

console = Console(legacy_windows=False)

PREDICTION_DIR = Path("data/predictions")
RESULTS_DIR = Path("data/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ACTUALS_FILE = RESULTS_DIR / "actuals.csv"


def get_price_on_or_after(ticker: str, target_date: date, tolerance_days: int = 5) -> tuple[float | None, str | None]:
    """
    Fetch closing price on target_date. If the market was closed (weekend/holiday),
    use the next available trading day within tolerance_days.
    Returns (price, actual_date_str) or (None, None) if unavailable.
    """
    end = target_date + timedelta(days=tolerance_days + 1)
    hist = yf.Ticker(ticker).history(start=target_date.isoformat(), end=end.isoformat())
    if hist.empty:
        return None, None
    row = hist.iloc[0]
    actual_date = hist.index[0].date().isoformat()
    return float(row["Close"]), actual_date


def load_predictions() -> list[dict]:
    records = []
    for path in sorted(PREDICTION_DIR.glob("*.json")):
        try:
            with open(path) as f:
                rec = json.load(f)
            records.append(rec)
        except Exception as e:
            console.print(f"[yellow]Skipping {path.name}: {e}[/yellow]")
    return records


def fetch_actuals(config: dict) -> pd.DataFrame:
    predictions = load_predictions()

    if not predictions:
        console.print("[red]No prediction files found in data/predictions/[/red]")
        return pd.DataFrame()

    rows = []
    seen = {}  # (ticker, target_date) -> actual price to avoid redundant API calls

    for rec in predictions:
        ticker = rec["ticker"]
        pred_date = date.fromisoformat(rec["date"])
        window = rec.get("window_days", config.get("prediction_window_days", 1))
        target_date = pred_date + timedelta(days=window)
        today = date.today()

        if target_date > today:
            console.print(f"[yellow]Window not closed for {ticker} predicted on {pred_date} (target: {target_date})[/yellow]")
            actual_price, actual_date = None, None
        else:
            key = (ticker, target_date.isoformat())
            if key not in seen:
                price, adate = get_price_on_or_after(ticker, target_date)
                seen[key] = (price, adate)
                if price:
                    console.print(f"[green]OK[/green] {ticker} on {adate}: ${price:.2f}")
                else:
                    console.print(f"[red]FAIL[/red] {ticker}: no data for {target_date}")
            actual_price, actual_date = seen[key]

        pred = rec.get("prediction") or {}
        reasoning = pred.get("reasoning", "")
        if "Mock" in reasoning or "dry-run" in reasoning:
            continue

        def ci(key):
            val = pred.get(key)
            return (val[0], val[1]) if val else (None, None)

        ci50 = ci("50_ci")
        ci80 = ci("80_ci")
        ci90 = ci("90_ci")
        rows.append({
            "model": rec["model"],
            "ticker": ticker,
            "pred_date": rec["date"],
            "run": rec["run"],
            "current_price": rec["current_price"],
            "window_days": rec["window_days"],
            "target_date": target_date.isoformat(),
            "actual_date": actual_date,
            "actual_price": actual_price,
            "point_estimate": pred.get("point_estimate"),
            "ci_50_low": ci50[0],
            "ci_50_high": ci50[1],
            "ci_80_low": ci80[0],
            "ci_80_high": ci80[1],
            "ci_90_low": ci90[0],
            "ci_90_high": ci90[1],
        })

    df = pd.DataFrame(rows)
    df.to_csv(ACTUALS_FILE, index=False)
    console.print(f"\n[bold]Saved actuals to {ACTUALS_FILE}[/bold] ({len(df)} rows)")
    return df


if __name__ == "__main__":
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    fetch_actuals(config)
