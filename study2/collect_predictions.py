"""
Collect AI model predictions for stock prices.
Prompts each configured model for confidence interval predictions and saves responses.
"""

import json
import time
import random
from datetime import date, timedelta
from pathlib import Path

import anthropic
import openai
from google import genai as google_genai
import yfinance as yf
import yaml
from dotenv import load_dotenv
import os
from rich.console import Console
from rich.progress import track

load_dotenv()
console = Console(legacy_windows=False)

PREDICTION_DIR = Path("data/predictions")
PREDICTION_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATE = """Today is {date}. The current price of {ticker} is ${price:.2f}.
Please predict the price in {window} days.
Give me three confidence intervals:
- 50% confidence interval: [low, high]
- 80% confidence interval: [low, high]
- 90% confidence interval: [low, high]
Respond ONLY in JSON:
{{
  "point_estimate": float,
  "50_ci": [float, float],
  "80_ci": [float, float],
  "90_ci": [float, float],
  "reasoning": string
}}"""

BACKTEST_PROMPT_TEMPLATE = """The current price of {ticker} is ${price:.2f}.
Please predict the price in {window} days.
Give me three confidence intervals:
- 50% confidence interval: [low, high]
- 80% confidence interval: [low, high]
- 90% confidence interval: [low, high]
Respond ONLY in JSON:
{{
  "point_estimate": float,
  "50_ci": [float, float],
  "80_ci": [float, float],
  "90_ci": [float, float],
  "reasoning": string
}}"""

MOCK_RESPONSE_TEMPLATE = {
    "point_estimate": None,  # filled dynamically
    "50_ci": None,
    "80_ci": None,
    "90_ci": None,
    "reasoning": "Mock response for dry-run testing.",
}


def get_current_price(ticker: str) -> float:
    data = yf.Ticker(ticker)
    hist = data.history(period="1d")
    if hist.empty:
        raise ValueError(f"No price data found for {ticker}")
    return float(hist["Close"].iloc[-1])


def get_historical_price(ticker: str, target_date: date) -> tuple[float | None, str | None]:
    """Fetch closing price on or before target_date (handles weekends/holidays)."""
    start = target_date - timedelta(days=7)
    hist = yf.Ticker(ticker).history(start=start.isoformat(), end=(target_date + timedelta(days=1)).isoformat())
    if hist.empty:
        return None, None
    row = hist.iloc[-1]
    actual_date = hist.index[-1].date().isoformat()
    return float(row["Close"]), actual_date


def make_mock_response(price: float) -> dict:
    spread_50 = price * 0.03
    spread_80 = price * 0.06
    spread_90 = price * 0.09
    point = round(price * (1 + random.uniform(-0.05, 0.05)), 2)
    return {
        "point_estimate": point,
        "50_ci": [round(price - spread_50, 2), round(price + spread_50, 2)],
        "80_ci": [round(price - spread_80, 2), round(price + spread_80, 2)],
        "90_ci": [round(price - spread_90, 2), round(price + spread_90, 2)],
        "reasoning": "Mock response for dry-run testing.",
    }


def parse_json_response(text: str) -> dict:
    """Extract JSON from model response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # strip opening and closing fences
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def call_with_retry(fn, retries=3, base_delay=2.0):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            console.print(f"[yellow]Retry {attempt + 1}/{retries} after error: {e}. Waiting {delay:.1f}s[/yellow]")
            time.sleep(delay)


def call_anthropic(model_id: str, prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _call():
        msg = client.messages.create(
            model=model_id,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    return call_with_retry(_call)


def call_openai(model_id: str, prompt: str) -> str:
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _call():
        resp = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return resp.choices[0].message.content

    return call_with_retry(_call)


def call_google(model_id: str, prompt: str) -> str:
    def _call():
        client = google_genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        resp = client.models.generate_content(model=model_id, contents=prompt)
        return resp.text

    return call_with_retry(_call)


def collect_prediction(model_cfg: dict, ticker: str, price: float, window: int, run: int, dry_run: bool, pred_date: str | None = None, backtest: bool = False) -> dict:
    if pred_date is None:
        pred_date = date.today().isoformat()

    if backtest:
        prompt = BACKTEST_PROMPT_TEMPLATE.format(ticker=ticker, price=price, window=window)
    else:
        prompt = PROMPT_TEMPLATE.format(date=pred_date, ticker=ticker, price=price, window=window)

    if dry_run:
        raw_response = json.dumps(make_mock_response(price))
        parsed = json.loads(raw_response)
    else:
        api = model_cfg["api"]
        model_id = model_cfg["model_id"]

        if api == "anthropic":
            raw_response = call_anthropic(model_id, prompt)
        elif api == "openai":
            raw_response = call_openai(model_id, prompt)
        elif api == "google":
            raw_response = call_google(model_id, prompt)
        else:
            raise ValueError(f"Unknown API: {api}")

        parsed = parse_json_response(raw_response)

    record = {
        "model": model_cfg["name"],
        "model_id": model_cfg["model_id"],
        "ticker": ticker,
        "date": pred_date,
        "run": run,
        "current_price": price,
        "window_days": window,
        "prediction": parsed,
        "raw_response": raw_response if not dry_run else None,
        "backtest": backtest,
    }

    filename = PREDICTION_DIR / f"{model_cfg['name']}_{ticker}_{pred_date}_w{window}_run{run}.json"
    with open(filename, "w") as f:
        json.dump(record, f, indent=2)

    return record


def generate_stratified_date_pairs(backtest_days: int, buckets: list, seed: int = 42, reference_date: date | None = None) -> list[tuple[date, date]]:
    """
    Sample (start_date, end_date) pairs stratified by window length.
    Both dates are weekdays within the lookback window; end_date < today.
    buckets: list of dicts with 'range' [low, high] and 'n' pairs to sample.
    Returns list of (start_date, end_date) tuples.
    """
    rng = random.Random(seed)
    today = reference_date or date.today()
    lookback_start = today - timedelta(days=backtest_days)

    weekdays = []
    d = lookback_start
    while d < today:
        if d.weekday() < 5:
            weekdays.append(d)
        d += timedelta(days=1)

    result = []
    for bucket in buckets:
        low, high = bucket["range"]
        n = bucket["n"]
        pool = []
        for start in weekdays:
            for end in weekdays:
                if start < end < today:
                    diff = (end - start).days
                    if low <= diff <= high:
                        pool.append((start, end))
        if len(pool) < n:
            console.print(f"[yellow]Warning: only {len(pool)} pairs in {low}-{high}d bucket, wanted {n}[/yellow]")
            n = len(pool)
        result.extend(rng.sample(pool, n))

    return result


def collect_all(config: dict, dry_run: bool = False, backtest: bool = False):
    models = config["models"]
    tickers = config["tickers"]
    runs = config["runs_per_ticker"]
    backtest_days = config.get("backtest_days", 35)

    if backtest:
        buckets = config.get("date_pair_buckets", [{"range": [1, 30], "n": 7}])
        seed = config.get("random_seed", 42)
        ref_date_str = config.get("reference_date")
        ref_date = date.fromisoformat(ref_date_str) if ref_date_str else None
        date_pairs = generate_stratified_date_pairs(backtest_days, buckets, seed, reference_date=ref_date)
        total = len(models) * len(tickers) * len(date_pairs) * runs
        console.print(f"[bold]Collecting predictions[/bold]: {len(models)} models x {len(tickers)} tickers x {len(date_pairs)} date pairs x {runs} runs = {total} calls")
        console.print(f"[cyan]BACKTEST mode — date blinded from models[/cyan]")
        console.print(f"[cyan]Sampled date pairs:[/cyan]")
        for start, end in date_pairs:
            window = (end - start).days
            console.print(f"  {start} -> {end} ({window}d window)")
    else:
        windows = config.get("prediction_windows", [config.get("prediction_window_days", 1)])
        date_pairs = [(date.today(), date.today() + timedelta(days=w)) for w in windows]
        total = len(models) * len(tickers) * len(date_pairs) * runs
        console.print(f"[bold]Collecting predictions[/bold]: {len(models)} models x {len(tickers)} tickers x {len(date_pairs)} windows x {runs} runs = {total} calls")

    if dry_run:
        console.print("[cyan]DRY RUN mode — using mock responses[/cyan]")

    # Pre-fetch all needed historical prices: one price per (ticker, start_date)
    start_dates = sorted(set(s for s, _ in date_pairs))
    prices_by_date = {}  # (ticker, start_date_str) -> price
    console.print(f"\nFetching historical prices for {len(tickers)} tickers x {len(start_dates)} start dates...")
    for start in start_dates:
        for ticker in tickers:
            try:
                price, actual_date = get_historical_price(ticker, start)
                if price is None:
                    raise ValueError(f"No data near {start}")
                prices_by_date[(ticker, actual_date)] = price
                prices_by_date[(ticker, start.isoformat())] = price  # fallback key
            except Exception as e:
                console.print(f"[red]Failed {ticker} on {start}: {e}[/red]")

    for model_cfg in models:
        for ticker in tickers:
            for start, end in date_pairs:
                window = (end - start).days
                price = prices_by_date.get((ticker, start.isoformat()))
                if price is None:
                    console.print(f"[yellow]Skipping {model_cfg['name']}/{ticker}/{start} — no price[/yellow]")
                    continue
                for run in range(1, runs + 1):
                    existing = PREDICTION_DIR / f"{model_cfg['name']}_{ticker}_{start.isoformat()}_w{window}_run{run}.json"
                    if existing.exists():
                        try:
                            rec = json.loads(existing.read_text())
                            if "Mock" not in rec.get("prediction", {}).get("reasoning", ""):
                                console.print(f"[dim]SKIP[/dim] {model_cfg['name']} / {ticker} / {start}->{end} ({window}d) / run {run}")
                                continue
                        except Exception:
                            pass
                    try:
                        collect_prediction(model_cfg, ticker, price, window, run, dry_run,
                                           pred_date=start.isoformat(), backtest=backtest)
                        console.print(f"[green]OK[/green] {model_cfg['name']} / {ticker} / {start}->{end} ({window}d) / run {run}")
                    except Exception as e:
                        console.print(f"[red]FAIL {model_cfg['name']} / {ticker} / {window}d / run {run}: {e}[/red]")
                    if not dry_run:
                        time.sleep(0.5)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backtest", action="store_true")
    args = parser.parse_args()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    collect_all(config, dry_run=args.dry_run, backtest=args.backtest)
