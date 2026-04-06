"""
collect_predictions.py — Study 4 daily prediction collection.

Makes two API calls per item × model:
  1. Prediction call: structured JSON with point estimates + CIs for all three horizons.
  2. Justification call: free-text explanation. Must be a SEPARATE call made AFTER
     the prediction response is received. Never merge these two calls.

Designed to be run from study4/ directory.
Usage:
  python collect_predictions.py [--date YYYY-MM-DD] [--dry-run]
  python collect_predictions.py --domain stocks --model claude
"""

import argparse
import json
import os
import random
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
import httpx
import openai
import requests
import urllib3
import yaml
from dotenv import load_dotenv
from google import genai as google_genai
from rich.console import Console

# ── Tulane corporate proxy: disable SSL verification (see global CLAUDE.md) ────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()
# Factory for fresh httpx clients with SSL verification disabled
def _make_httpx():
    return httpx.Client(verify=False, timeout=90.0)

load_dotenv()

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

BASE_DIR       = Path(__file__).parent
PREDICTIONS_DIR = BASE_DIR / "data" / "predictions"
LOGS_DIR       = BASE_DIR / "logs"

# ── Prompt versioning ──────────────────────────────────────────────────────────
# Increment PROMPT_VERSION whenever prompt wording changes. Any change is a
# methodological event and should be noted in config.yaml model_version_changes.
PROMPT_VERSION = "2.0.0"

PREDICTION_PROMPT = """\
Today is {date}.

{context}

Predict the closing price of {item_label} at three future horizons. For each horizon, \
provide a point estimate and a 90% confidence interval. A 90% confidence interval \
means you are providing a low value and a high value such that you believe there is \
a 90% chance the true closing price will fall between them. If we asked you to make \
this kind of estimate 100 times, the true value should fall inside your interval on \
about 90 of those occasions. Choose your bounds accordingly.

Horizons:
  1-day  target date: {date_1d}
  1-week target date: {date_1w}
  1-month target date: {date_1m}

Respond ONLY with valid JSON and no markdown fences:
{{
  "1d": {{
    "point_estimate": <number>,
    "90_ci": [<low>, <high>]
  }},
  "1w": {{
    "point_estimate": <number>,
    "90_ci": [<low>, <high>]
  }},
  "1m": {{
    "point_estimate": <number>,
    "90_ci": [<low>, <high>]
  }}
}}"""

JUSTIFICATION_PROMPT = """\
You previously made the following probabilistic forecast:

{prediction_json}

Please explain your reasoning in 2–4 paragraphs. Address:
1. What drove your point estimates at each horizon?
2. What sources of uncertainty influenced your confidence interval widths?
3. Are there specific risks or events that could push outcomes outside your stated intervals?

Write in plain English. No JSON, no bullet points."""


# ── Reference value fetching ───────────────────────────────────────────────────

def _get_yesterday_mean_temp(lat: float, lon: float) -> float:
    """Daily mean temperature for yesterday from Open-Meteo archive (°F)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": yesterday, "end_date": yesterday,
        "daily": "temperature_2m_mean",
        "temperature_unit": "fahrenheit",
    }
    resp = requests.get(url, params=params, timeout=20, verify=False)
    resp.raise_for_status()
    data = resp.json()
    return float(data["daily"]["temperature_2m_mean"][0])


def get_reference_value(item_cfg: dict, domain: str) -> float:
    """Fetch current reference value for the item. Raises on failure."""
    import yfinance as yf

    if domain == "stocks":
        yf_ticker = item_cfg.get("yfinance_ticker", item_cfg["id"])
        ticker = yf.Ticker(yf_ticker)
        return float(ticker.fast_info["lastPrice"])

    if domain == "forex":
        yf_ticker = item_cfg.get("yfinance_ticker", item_cfg["id"])
        ticker = yf.Ticker(yf_ticker)
        return float(ticker.fast_info["lastPrice"])

    if domain == "crypto":
        coin_id = item_cfg["coingecko_id"]
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coin_id, "vs_currencies": "usd"}
        resp = requests.get(url, params=params, timeout=20, verify=False)
        resp.raise_for_status()
        return float(resp.json()[coin_id]["usd"])

    if domain == "weather":
        return _get_yesterday_mean_temp(item_cfg["lat"], item_cfg["lon"])

    raise ValueError(f"Unknown domain: {domain}")


def build_context(item_cfg: dict, domain: str, domain_cfg: dict,
                  ref_val: float, run_date: date) -> str:
    unit = domain_cfg["unit"]
    item_id = item_cfg["id"]
    label = item_cfg.get("label", item_id)

    if domain == "stocks":
        return f"Current closing price of {label} ({item_id}): ${ref_val:.2f} USD as of {run_date}."
    if domain == "crypto":
        fmt = f"${ref_val:.4f}" if ref_val < 1 else f"${ref_val:.2f}"
        return f"Current USD price of {label} ({item_id}): {fmt} as of {run_date}."
    if domain == "forex":
        return f"Current exchange rate for {item_id}: {ref_val:.4f} as of {run_date}."
    if domain == "weather":
        return (
            f"Yesterday's mean daily temperature in {label}: "
            f"{ref_val:.1f}°F (as of {run_date - timedelta(days=1)}). "
            f"Predict the mean daily temperature for the target dates below."
        )
    return f"Current value of {item_id}: {ref_val} {unit} as of {run_date}."


# ── API calling ────────────────────────────────────────────────────────────────

def parse_json_response(text: str) -> dict:
    import re
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.startswith("```")]
        text = "\n".join(lines).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract first JSON object from surrounding text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No valid JSON found in response: {text[:200]}")


def call_with_retry(fn, retries: int = 3, base_delay: float = 2.0):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            console.print(f"  [yellow]Retry {attempt+1}/{retries}: {e}. Waiting {delay:.1f}s[/yellow]")
            time.sleep(delay)


def call_model(model_cfg: dict, prompt: str, max_tokens: int = 1024) -> str:
    api = model_cfg["api"]
    model_id = model_cfg["model_id"]

    if api == "anthropic":
        client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            http_client=_make_httpx(),
        )
        def _call():
            msg = client.messages.create(
                model=model_id, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text

    elif api == "openai":
        client = openai.OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            http_client=_make_httpx(),
        )
        def _call():
            resp = client.chat.completions.create(
                model=model_id, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content

    elif api == "google":
        def _call():
            client = google_genai.Client(
                api_key=os.environ["GOOGLE_API_KEY"],
                http_options={"api_version": "v1beta"},
            )
            return client.models.generate_content(model=model_id, contents=prompt).text

    else:
        raise ValueError(f"Unknown API: {api}")

    return call_with_retry(_call)


def make_mock_prediction(ref_val: float, run_date: date) -> dict:
    spread = max(ref_val * 0.04, 0.01)
    result = {}
    for horizon_id, days in [("1d", 1), ("1w", 7), ("1m", 30)]:
        pt = round(ref_val * (1 + random.uniform(-0.02, 0.02)), 6)
        result[horizon_id] = {
            "point_estimate": pt,
            "90_ci": [round(pt - spread * 1.5, 6),  round(pt + spread * 1.5, 6)],
        }
    return result


# ── Collection logic ───────────────────────────────────────────────────────────

def safe_item_id(item_cfg: dict, domain: str) -> str:
    """Filesystem-safe item identifier."""
    return item_cfg.get("safe_id", item_cfg["id"]).replace("-", "_")


def collect_item(item_cfg: dict, domain: str, domain_cfg: dict,
                 model_cfg: dict, run_date: date,
                 dry_run: bool = False) -> dict:
    """
    Collect prediction + justification for one item × model.
    Returns a record dict; sets status='failed' on any error.
    The justification is always a SEPARATE API call made after prediction.
    """
    item_id    = item_cfg["id"]
    model_name = model_cfg["name"]
    log_tag    = f"[{model_name}][{domain}][{item_id}]"

    record = {
        "model":              model_name,
        "model_id":           model_cfg["model_id"],
        "prompt_version":     PROMPT_VERSION,
        "pred_date":          run_date.isoformat(),
        "timestamp":          datetime.utcnow().isoformat() + "Z",
        "domain":             domain,
        "item":               item_id,
        "item_label":         item_cfg.get("label", item_id),
        "unit":               domain_cfg["unit"],
        "current_value":      None,
        "context":            None,
        "prompt_text":        None,
        "raw_response":       None,
        "horizons":           None,
        "justification_prompt": None,
        "justification_text": None,
        "status":             "failed",
        "error":              None,
    }

    try:
        # ── Step 1: reference value ───────────────────────────────────────────
        if not dry_run:
            ref_val = get_reference_value(item_cfg, domain)
        else:
            ref_val = 100.0
        record["current_value"] = ref_val
        console.print(f"  {log_tag} ref={ref_val}")

        # ── Step 2: build prediction prompt ──────────────────────────────────
        context = build_context(item_cfg, domain, domain_cfg, ref_val, run_date)
        record["context"] = context

        date_1d = (run_date + timedelta(days=1)).isoformat()
        date_1w = (run_date + timedelta(days=7)).isoformat()
        date_1m = (run_date + timedelta(days=30)).isoformat()

        prompt = PREDICTION_PROMPT.format(
            date=run_date.isoformat(),
            context=context,
            item_label=item_cfg.get("label", item_id),
            date_1d=date_1d, date_1w=date_1w, date_1m=date_1m,
        )
        record["prompt_text"] = prompt

        # ── Step 3: prediction API call ───────────────────────────────────────
        if not dry_run:
            raw = call_model(model_cfg, prompt, max_tokens=1024)
            parsed = parse_json_response(raw)
        else:
            parsed = make_mock_prediction(ref_val, run_date)
            raw = json.dumps(parsed)

        record["raw_response"] = raw
        record["horizons"]     = parsed

        # ── Step 4: justification API call (SEPARATE from prediction) ─────────
        # The prediction response MUST be received before this call is made.
        # Do not combine these into a single API call.
        just_prompt = JUSTIFICATION_PROMPT.format(
            prediction_json=json.dumps(parsed, indent=2)
        )
        record["justification_prompt"] = just_prompt

        if not dry_run:
            just_text = call_model(model_cfg, just_prompt, max_tokens=600)
        else:
            just_text = "Dry-run mode — no justification generated."
        record["justification_text"] = just_text

        record["status"] = "collected"
        console.print(f"  [green]OK[/green] {log_tag}")

    except Exception as e:
        record["status"] = "failed"
        record["error"]  = str(e)
        console.print(f"  [red]FAIL[/red] {log_tag}: {e}")

    return record


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Collect Study 4 predictions")
    parser.add_argument("--date",    help="Override collection date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Mock responses, no API calls")
    parser.add_argument("--domain",  help="Collect only this domain")
    parser.add_argument("--model",   help="Collect only this model (short name, e.g. claude)")
    args = parser.parse_args()

    with open(BASE_DIR / "config.yaml") as f:
        config = yaml.safe_load(f)

    run_date = date.fromisoformat(args.date) if args.date else date.today()
    is_weekend = run_date.weekday() >= 5

    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    console.print(f"\n[bold]Study 4 collection — {run_date}[/bold]"
                  + (" [cyan](dry-run)[/cyan]" if args.dry_run else ""))
    if is_weekend:
        console.print("[yellow]Weekend — financial domains will be skipped unless overridden[/yellow]")

    total = collected = failed = skipped = 0

    for domain, domain_cfg in config["domains"].items():
        if not domain_cfg.get("enabled", True):
            continue
        if args.domain and domain != args.domain:
            continue

        # Weekend skip
        is_financial = domain in ("stocks", "crypto", "forex")
        if is_weekend and is_financial and not config["weekend_collection"]["financial"]:
            n = len(domain_cfg["items"]) * len(config["models"])
            skipped += n
            console.print(f"[dim]Skipping {domain} (weekend)[/dim]")
            continue
        if is_weekend and domain == "weather" and not config["weekend_collection"]["weather"]:
            n = len(domain_cfg["items"]) * len(config["models"])
            skipped += n
            console.print(f"[dim]Skipping weather (weekend, config=false)[/dim]")
            continue

        console.print(f"\n[bold blue]Domain: {domain}[/bold blue]")

        for item_cfg in domain_cfg["items"]:
            # CoinGecko free API rate limit: pause between crypto items
            # Free tier allows ~10-30 calls/min; we need 1 ref call + 2 model calls per item×model
            if domain == "crypto" and not args.dry_run:
                time.sleep(8)

            for model_cfg in config["models"]:
                if args.model and model_cfg["name"] != args.model:
                    continue

                sid = safe_item_id(item_cfg, domain)
                filename = (
                    PREDICTIONS_DIR
                    / f"{model_cfg['name']}_{domain}_{sid}_{run_date.isoformat()}.json"
                )
                if filename.exists():
                    console.print(f"  [dim]SKIP[/dim] {model_cfg['name']}_{domain}_{sid} (exists)")
                    skipped += 1
                    continue

                total += 1
                record = collect_item(
                    item_cfg, domain, domain_cfg,
                    model_cfg, run_date, dry_run=args.dry_run,
                )
                filename.write_text(json.dumps(record, indent=2))

                if record["status"] == "collected":
                    collected += 1
                else:
                    failed += 1

                if not args.dry_run:
                    time.sleep(0.5)

    console.print(
        f"\n[bold]Done:[/bold] {collected} collected, {failed} failed, {skipped} skipped"
        f" (total attempted: {total})"
    )
    if collected == 0 and failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
