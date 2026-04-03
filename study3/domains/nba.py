"""
NBA domain: predict total points scored in tomorrow's games.
Ground truth: ESPN unofficial scoreboard API (no auth required).
Auto-disabled if no games are scheduled for the target date.
"""
from datetime import date, timedelta

import requests

from .base import Question

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def _get_games(game_date: date) -> list[dict]:
    resp = requests.get(
        ESPN_SCOREBOARD,
        params={"dates": game_date.strftime("%Y%m%d")},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("events", [])


def generate_questions(config: dict, pred_date: date) -> list[Question]:
    if not config.get("domains", {}).get("nba", {}).get("enabled", True):
        return []

    target_date = pred_date + timedelta(days=1)
    try:
        games = _get_games(target_date)
    except Exception:
        return []

    questions = []
    for game in games:
        try:
            comp = game["competitions"][0]
            competitors = comp["competitors"]
            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")

            home_name = home["team"]["displayName"]
            away_name = away["team"]["displayName"]
            home_abbr = home["team"]["abbreviation"]
            away_abbr = away["team"]["abbreviation"]

            def record(c):
                recs = c.get("records") or []
                return recs[0].get("summary", "?-?") if recs else "?-?"

            home_rec = record(home)
            away_rec = record(away)

            qid = f"nba_{away_abbr}_{home_abbr}_{target_date.isoformat()}"
            questions.append(Question(
                domain="nba",
                question_id=qid,
                question_text=(
                    f"How many total points will be scored in the NBA game between "
                    f"{away_name} and {home_name} on {target_date.isoformat()}?"
                ),
                context=(
                    f"{away_name} ({away_rec}) at {home_name} ({home_rec}). "
                    f"Regular season NBA game."
                ),
                unit="total points",
                current_value=0.0,
                target_date=target_date.isoformat(),
                metadata={
                    "home_team": home_name,
                    "away_team": away_name,
                    "home_abbr": home_abbr,
                    "away_abbr": away_abbr,
                    "espn_game_id": game.get("id"),
                },
            ))
        except Exception:
            pass

    return questions


def fetch_actual(question: Question) -> tuple[float | None, str | None]:
    target = date.fromisoformat(question.target_date)
    home_abbr = question.metadata["home_abbr"]
    away_abbr = question.metadata["away_abbr"]

    try:
        games = _get_games(target)
        for game in games:
            comp = game["competitions"][0]
            competitors = comp["competitors"]
            home = next((c for c in competitors if c["homeAway"] == "home"), None)
            away = next((c for c in competitors if c["homeAway"] == "away"), None)
            if home is None or away is None:
                continue
            if (home["team"]["abbreviation"] == home_abbr
                    and away["team"]["abbreviation"] == away_abbr):
                if not comp.get("status", {}).get("type", {}).get("completed", False):
                    return None, None  # game not finished yet
                total = int(home.get("score", 0)) + int(away.get("score", 0))
                return float(total), target.isoformat()
    except Exception:
        pass

    return None, None
