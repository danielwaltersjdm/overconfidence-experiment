"""
fetch_actuals.py — Study 5: pull final-state stats from MLB Stats API for
every prediction that has a finished game.

Iterates over all prediction files, dedupes by game_pk, queries the
boxscore + live feed for each finished game, and writes per-game actuals
to data/actuals/actuals.csv.

Usage (from study5/):
  python fetch_actuals.py
"""

import csv
import json
import ssl
import sys
import urllib.request
from pathlib import Path

from rich.console import Console

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(legacy_windows=False)

BASE_DIR = Path(__file__).parent
PRED_DIR = BASE_DIR / "data" / "predictions"
ACTUALS_DIR = BASE_DIR / "data" / "actuals"
ACTUALS_FILE = ACTUALS_DIR / "actuals.csv"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

QUANTITIES = ["total_runs", "total_strikeouts", "total_home_runs",
              "duration_min", "attendance"]


def fetch_boxscore(pk: int) -> dict:
    url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
    with urllib.request.urlopen(url, context=_SSL_CTX, timeout=30) as r:
        return json.load(r)


def fetch_feed(pk: int) -> dict:
    url = f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
    with urllib.request.urlopen(url, context=_SSL_CTX, timeout=30) as r:
        return json.load(r)


def extract_actuals(pk: int) -> tuple[str, dict | None]:
    """Return (status, actuals_dict_or_None).
    status is one of: 'resolved', 'pending', 'fetch_error'.
    """
    try:
        box = fetch_boxscore(pk)
        feed = fetch_feed(pk)
    except Exception as e:
        return ("fetch_error", {"error": str(e)})

    state = feed.get("gameData", {}).get("status", {}).get("detailedState", "")
    if state != "Final":
        return ("pending", {"detailedState": state})

    try:
        bs_h = box["teams"]["home"]["teamStats"]
        bs_a = box["teams"]["away"]["teamStats"]
        gi = feed["gameData"]["gameInfo"]
        actuals = {
            "total_runs":       bs_h["batting"]["runs"] + bs_a["batting"]["runs"],
            "total_strikeouts": bs_h["batting"]["strikeOuts"] + bs_a["batting"]["strikeOuts"],
            "total_home_runs":  bs_h["batting"]["homeRuns"] + bs_a["batting"]["homeRuns"],
            "duration_min":     gi.get("gameDurationMinutes"),
            "attendance":       gi.get("attendance"),
        }
        # Verify all five are present
        missing = [q for q in QUANTITIES if actuals.get(q) is None]
        if missing:
            return ("fetch_error", {"error": f"missing values: {missing}"})
        return ("resolved", actuals)
    except (KeyError, TypeError) as e:
        return ("fetch_error", {"error": f"parse error: {e}"})


def main():
    if not PRED_DIR.exists():
        console.print(f"[red]No predictions directory: {PRED_DIR}[/red]")
        return

    # Dedupe game_pks across prediction files
    game_meta = {}
    for f in sorted(PRED_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        d = json.loads(f.read_text())
        pk = d.get("game_pk")
        if pk is None:
            continue
        game_meta.setdefault(pk, {
            "game_pk":     pk,
            "game_date":   d.get("game_date"),
            "away_team":   d.get("away_team"),
            "home_team":   d.get("home_team"),
            "venue":       d.get("venue"),
        })

    console.print(f"[bold]Unique games to check:[/bold] {len(game_meta)}")

    # Load existing resolutions to skip
    existing = {}
    if ACTUALS_FILE.exists():
        with open(ACTUALS_FILE, "r", newline="") as f:
            for row in csv.DictReader(f):
                existing[int(row["game_pk"])] = row
        console.print(f"  Existing resolved: {sum(1 for r in existing.values() if r.get('status')=='resolved')}")

    ACTUALS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    n_new = n_pending = n_err = 0
    for pk, meta in sorted(game_meta.items()):
        # Skip already-resolved (idempotent)
        if pk in existing and existing[pk].get("status") == "resolved":
            rows.append(existing[pk])
            continue

        status, result = extract_actuals(pk)
        row = dict(meta, status=status)
        if status == "resolved":
            row.update({q: result[q] for q in QUANTITIES})
            n_new += 1
            console.print(f"  [green]OK[/green] pk={pk} {meta['away_team']} @ {meta['home_team']} ({meta['game_date']})  runs={result['total_runs']}")
        elif status == "pending":
            row["note"] = result.get("detailedState", "")
            n_pending += 1
        else:
            row["error"] = result.get("error", "")
            n_err += 1
            console.print(f"  [red]ERR[/red] pk={pk}: {result.get('error')[:80]}")
        rows.append(row)

    # Write actuals CSV
    fieldnames = ["game_pk", "game_date", "away_team", "home_team", "venue",
                  "status"] + QUANTITIES + ["note", "error"]
    with open(ACTUALS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    console.print(f"\n[bold]Done[/bold]: {n_new} newly resolved, {n_pending} pending, {n_err} fetch errors")
    console.print(f"  Total rows written: {len(rows)} → {ACTUALS_FILE}")


if __name__ == "__main__":
    main()
