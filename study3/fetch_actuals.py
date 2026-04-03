"""
Fetch actual outcomes for all saved predictions.
Routes each prediction to its domain's fetch_actual function and writes actuals.csv.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console(legacy_windows=False)

PREDICTION_DIR = Path("data/predictions")
RESULTS_DIR = Path("data/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
ACTUALS_FILE = RESULTS_DIR / "actuals.csv"


def load_predictions() -> list[dict]:
    records = []
    for path in sorted(PREDICTION_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text()))
        except Exception as e:
            console.print(f"[yellow]Skipping {path.name}: {e}[/yellow]")
    return records


def fetch_actuals() -> pd.DataFrame:
    from domains import fetch_actual_for_question
    from domains.base import Question

    predictions = load_predictions()
    if not predictions:
        console.print("[red]No prediction files found in data/predictions/[/red]")
        return pd.DataFrame()

    today = date.today().isoformat()
    rows = []
    cache: dict[str, tuple] = {}  # question_id -> (actual_value, actual_date)

    for rec in predictions:
        question = Question.from_dict(rec["question"])

        if question.target_date > today:
            console.print(
                f"[yellow]Not resolved yet: {question.question_id} "
                f"(target: {question.target_date})[/yellow]"
            )
            actual_value, actual_date = None, None
        else:
            if question.question_id not in cache:
                try:
                    val, adate = fetch_actual_for_question(question)
                    cache[question.question_id] = (val, adate)
                    if val is not None:
                        console.print(
                            f"[green]OK[/green] {question.question_id}: {val:.4g} on {adate}"
                        )
                    else:
                        console.print(f"[red]FAIL[/red] {question.question_id}: no data")
                except Exception as e:
                    console.print(f"[red]ERROR[/red] {question.question_id}: {e}")
                    cache[question.question_id] = (None, None)
            actual_value, actual_date = cache[question.question_id]

        pred = rec["prediction"]

        def ci(level):
            vals = pred.get(f"{level}_ci", [None, None])
            return (vals[0] if vals else None), (vals[1] if vals else None)

        lo50, hi50 = ci(50)
        lo80, hi80 = ci(80)
        lo90, hi90 = ci(90)

        rows.append({
            "model":          rec["model"],
            "domain":         question.domain,
            "question_id":    question.question_id,
            "pred_date":      rec["pred_date"],
            "target_date":    question.target_date,
            "actual_date":    actual_date,
            "unit":           question.unit,
            "current_value":  question.current_value,
            "actual_value":   actual_value,
            "point_estimate": pred.get("point_estimate"),
            "ci_50_low":      lo50,
            "ci_50_high":     hi50,
            "ci_80_low":      lo80,
            "ci_80_high":     hi80,
            "ci_90_low":      lo90,
            "ci_90_high":     hi90,
        })

    df = pd.DataFrame(rows)
    df.to_csv(ACTUALS_FILE, index=False)
    console.print(f"\n[bold]Saved {len(df)} rows to {ACTUALS_FILE}[/bold]")
    return df


if __name__ == "__main__":
    fetch_actuals()
