"""
collect_predictions.py — Study 5: MLB Game Outcome Calibration

For every scheduled MLB game in a window, prompt each of three frontier
LLMs for a point estimate and 90% confidence interval on five quantities:
  - Total runs
  - Total strikeouts
  - Total home runs
  - Game duration (minutes)
  - Attendance

All predictions are made today (single-shot batch) for games occurring
between START_DATE and END_DATE. Actuals are fetched and scored later
via fetch_actuals.py + score.py.

Usage (from study5/):
  python collect_predictions.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                                [--model claude|gpt4o|gemini]
                                [--dry-run]

Output: data/predictions/<model>_<gamepk>.json  (one per model x game)
"""

import argparse
import json
import os
import random
import ssl
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
import httpx
import openai
import urllib3
import requests
from dotenv import load_dotenv
from google import genai as google_genai
from rich.console import Console

# ── Tulane corporate proxy: disable SSL verification ───────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _httpx():
    return httpx.Client(verify=False, timeout=90.0)


load_dotenv(Path(__file__).parent.parent / ".env", override=True)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

BASE_DIR = Path(__file__).parent
PRED_DIR = BASE_DIR / "data" / "predictions"
LOG_DIR = BASE_DIR / "logs"

PROMPT_VERSION = "5.0.0"

# ── Models ────────────────────────────────────────────────────────────────
MODELS = [
    {"name": "claude", "api": "anthropic", "model_id": "claude-sonnet-4-6"},
    {"name": "gpt4o",  "api": "openai",    "model_id": "gpt-4o-2024-11-20"},
    {"name": "gemini", "api": "google",    "model_id": "gemini-2.5-flash"},
]

# ── Quantities (5 per game) ───────────────────────────────────────────────
QUANTITIES = ["total_runs", "total_strikeouts", "total_home_runs",
              "duration_min", "attendance"]

QUANTITY_DESCRIPTIONS = {
    "total_runs":       "Total runs scored in the game (both teams combined)",
    "total_strikeouts": "Total batter strikeouts in the game (both teams combined)",
    "total_home_runs":  "Total home runs hit in the game (both teams combined)",
    "duration_min":     "Game duration in minutes (from first pitch to final out, "
                        "including replays and pitching changes; excludes pre/post-game)",
    "attendance":       "Paid attendance at the game (announced figure)",
}

PROMPT_TEMPLATE = """\
Today is {today}.

You are forecasting outcomes of a Major League Baseball regular-season game.

Game details:
  Date:        {game_date}
  Matchup:     {away_team} at {home_team}
  Venue:       {venue}
  First pitch: {first_pitch} (game time)

Predict the following five quantities for this game. For each, provide a \
point estimate and a 90% confidence interval. A 90% confidence interval means \
you are providing a low value and a high value such that you believe there is \
a 90% chance the true value will fall between them. If we asked you to make \
this kind of estimate 100 times, the true value should fall inside your \
interval on about 90 of those occasions. Choose your bounds accordingly.

Quantities:
  1. total_runs        — {desc_total_runs}
  2. total_strikeouts  — {desc_total_strikeouts}
  3. total_home_runs   — {desc_total_home_runs}
  4. duration_min      — {desc_duration_min}
  5. attendance        — {desc_attendance}

Respond ONLY with valid JSON and no markdown fences:
{{
  "total_runs":       {{"point_estimate": <number>, "90_ci": [<low>, <high>]}},
  "total_strikeouts": {{"point_estimate": <number>, "90_ci": [<low>, <high>]}},
  "total_home_runs":  {{"point_estimate": <number>, "90_ci": [<low>, <high>]}},
  "duration_min":     {{"point_estimate": <number>, "90_ci": [<low>, <high>]}},
  "attendance":       {{"point_estimate": <number>, "90_ci": [<low>, <high>]}}
}}"""


# ── Schedule fetch ────────────────────────────────────────────────────────
def fetch_schedule(start: date, end: date) -> list[dict]:
    """Fetch MLB regular-season games in [start, end] inclusive."""
    url = (f"https://statsapi.mlb.com/api/v1/schedule"
           f"?sportId=1&startDate={start.isoformat()}&endDate={end.isoformat()}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as r:
        data = json.load(r)

    games = []
    for db in data.get("dates", []):
        date_str = db.get("date", "")
        for g in db.get("games", []):
            if g.get("gameType") != "R":
                continue
            games.append({
                "game_pk":     g["gamePk"],
                "game_date":   date_str,
                "first_pitch": g.get("gameDate", ""),
                "away_team":   g["teams"]["away"]["team"]["name"],
                "home_team":   g["teams"]["home"]["team"]["name"],
                "venue":       g.get("venue", {}).get("name", ""),
            })
    return games


# ── Response parsing ──────────────────────────────────────────────────────
def parse_json_response(text: str) -> dict:
    import re
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No valid JSON in response: {text[:200]}")


def validate_response(parsed: dict) -> None:
    """Ensure parsed response has all 5 quantities with point_estimate and 90_ci."""
    for q in QUANTITIES:
        if q not in parsed:
            raise ValueError(f"Missing quantity '{q}' in response")
        block = parsed[q]
        if not isinstance(block, dict):
            raise ValueError(f"'{q}' is not a JSON object")
        if "point_estimate" not in block:
            raise ValueError(f"'{q}' missing point_estimate")
        if "90_ci" not in block:
            raise ValueError(f"'{q}' missing 90_ci")
        if not isinstance(block["90_ci"], list) or len(block["90_ci"]) != 2:
            raise ValueError(f"'{q}' 90_ci must be [low, high]")


# ── Retry wrapper ─────────────────────────────────────────────────────────
def call_with_retry(fn, retries: int = 3, base_delay: float = 2.0):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            err = str(e).lower()
            if "503" in err or "unavailable" in err or "rate" in err:
                delay = min(60.0, 10.0 * (3 ** attempt)) + random.uniform(0, 3)
            else:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            console.print(f"    [yellow]retry {attempt+1}/{retries}: {str(e)[:80]}  waiting {delay:.1f}s[/yellow]")
            time.sleep(delay)


# ── Model calls ───────────────────────────────────────────────────────────
def call_model(model_cfg: dict, prompt: str, max_tokens: int = 1024) -> str:
    api = model_cfg["api"]
    model_id = model_cfg["model_id"]

    if api == "anthropic":
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"],
                                     http_client=_httpx())
        def _call():
            msg = client.messages.create(
                model=model_id, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text

    elif api == "openai":
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"],
                               http_client=_httpx())
        def _call():
            resp = client.chat.completions.create(
                model=model_id, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content

    elif api == "google":
        def _call():
            client = google_genai.Client(api_key=os.environ["GOOGLE_API_KEY"],
                                         http_options={"api_version": "v1beta"})
            return client.models.generate_content(model=model_id, contents=prompt).text

    else:
        raise ValueError(f"Unknown API: {api}")

    return call_with_retry(_call)


# ── Per-game collection ────────────────────────────────────────────────────
def build_prompt(game: dict, today: date) -> str:
    return PROMPT_TEMPLATE.format(
        today=today.isoformat(),
        game_date=game["game_date"],
        away_team=game["away_team"],
        home_team=game["home_team"],
        venue=game["venue"],
        first_pitch=game["first_pitch"],
        desc_total_runs=QUANTITY_DESCRIPTIONS["total_runs"],
        desc_total_strikeouts=QUANTITY_DESCRIPTIONS["total_strikeouts"],
        desc_total_home_runs=QUANTITY_DESCRIPTIONS["total_home_runs"],
        desc_duration_min=QUANTITY_DESCRIPTIONS["duration_min"],
        desc_attendance=QUANTITY_DESCRIPTIONS["attendance"],
    )


def collect_one(model_cfg: dict, game: dict, today: date, dry_run: bool) -> dict:
    record = {
        "model":          model_cfg["name"],
        "model_id":       model_cfg["model_id"],
        "prompt_version": PROMPT_VERSION,
        "pred_date":      today.isoformat(),
        "timestamp":      datetime.utcnow().isoformat() + "Z",
        "game_pk":        game["game_pk"],
        "game_date":      game["game_date"],
        "first_pitch":    game["first_pitch"],
        "away_team":      game["away_team"],
        "home_team":      game["home_team"],
        "venue":          game["venue"],
        "prompt_text":    None,
        "raw_response":   None,
        "predictions":    None,
        "status":         "failed",
        "error":          None,
    }

    try:
        prompt = build_prompt(game, today)
        record["prompt_text"] = prompt

        if dry_run:
            parsed = {q: {"point_estimate": 0, "90_ci": [0, 0]} for q in QUANTITIES}
            raw = json.dumps(parsed)
        else:
            raw = call_model(model_cfg, prompt, max_tokens=1024)
            parsed = parse_json_response(raw)
            validate_response(parsed)

        record["raw_response"] = raw
        record["predictions"] = parsed
        record["status"] = "collected"

    except Exception as e:
        record["status"] = "failed"
        record["error"] = str(e)

    return record


def filename_for(model_name: str, game_pk: int) -> Path:
    return PRED_DIR / f"{model_name}_{game_pk}.json"


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="Start date YYYY-MM-DD (default: tomorrow)")
    parser.add_argument("--end",   help="End date YYYY-MM-DD (default: start + 13 days)")
    parser.add_argument("--model", help="Restrict to one model (claude/gpt4o/gemini)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Re-attempt items whose existing file has status=failed")
    args = parser.parse_args()

    today = date.today()
    start = date.fromisoformat(args.start) if args.start else today + timedelta(days=1)
    end   = date.fromisoformat(args.end) if args.end else start + timedelta(days=13)

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    models = [m for m in MODELS if not args.model or m["name"] == args.model]

    console.print(f"[bold]Study 5 batch prediction collection[/bold]")
    console.print(f"  pred_date:  {today}")
    console.print(f"  window:     {start} -> {end} ({(end-start).days + 1} days)")
    console.print(f"  models:     {[m['name'] for m in models]}")
    console.print(f"  dry_run:    {args.dry_run}")

    console.print(f"\n[bold]Fetching MLB schedule...[/bold]")
    games = fetch_schedule(start, end)
    console.print(f"  Found {len(games)} regular-season games")

    total = len(games) * len(models)
    n_collected = n_failed = n_skipped = 0

    console.print(f"\n[bold]Collecting {total} predictions[/bold] ({len(games)} games x {len(models)} models)\n")

    for i, game in enumerate(games):
        for model_cfg in models:
            fname = filename_for(model_cfg["name"], game["game_pk"])

            if fname.exists():
                try:
                    existing = json.loads(fname.read_text())
                    if existing.get("status") == "collected":
                        console.print(f"  [dim]SKIP[/dim] {model_cfg['name']}/{game['game_pk']} (already collected)")
                        n_skipped += 1
                        continue
                    if not args.retry_failed:
                        console.print(f"  [dim]SKIP[/dim] {model_cfg['name']}/{game['game_pk']} (failed, use --retry-failed)")
                        n_skipped += 1
                        continue
                    console.print(f"  [yellow]RETRY[/yellow] {model_cfg['name']}/{game['game_pk']}")
                except (json.JSONDecodeError, OSError):
                    pass

            console.print(f"  [{i+1}/{len(games)}] {model_cfg['name']:8s} {game['away_team']} @ {game['home_team']} ({game['game_date']})")
            rec = collect_one(model_cfg, game, today, args.dry_run)
            fname.write_text(json.dumps(rec, indent=2))

            if rec["status"] == "collected":
                n_collected += 1
                # Show one quantity as a sanity check
                tr = rec["predictions"].get("total_runs", {})
                console.print(f"    [green]OK[/green]  total_runs={tr.get('point_estimate')} CI={tr.get('90_ci')}")
            else:
                n_failed += 1
                console.print(f"    [red]FAIL[/red] {rec['error'][:120]}")

            if not args.dry_run:
                time.sleep(0.3)

    console.print(f"\n[bold]Done[/bold]: {n_collected} collected, {n_failed} failed, {n_skipped} skipped (of {total})")
    if n_failed > 0:
        console.print(f"[yellow]Re-run with --retry-failed to re-attempt failures.[/yellow]")


if __name__ == "__main__":
    main()
