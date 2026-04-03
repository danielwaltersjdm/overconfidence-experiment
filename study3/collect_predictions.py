"""
Collect AI model predictions across all domains.
Generates questions for today, prompts each model, and saves JSON prediction files.
"""
import json
import os
import random
import time
from datetime import date
from pathlib import Path

import anthropic
import openai
import yaml
from dotenv import load_dotenv
from google import genai as google_genai
from rich.console import Console

load_dotenv()
console = Console(legacy_windows=False)

PREDICTION_DIR = Path("data/predictions")
PREDICTION_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATE = """Today is {date}.

{context}

Question: {question_text}

Provide a point estimate and three confidence intervals. Express all values in {unit}.

Respond ONLY in valid JSON with no markdown fences:
{{
  "point_estimate": <number>,
  "50_ci": [<low>, <high>],
  "80_ci": [<low>, <high>],
  "90_ci": [<low>, <high>],
  "reasoning": "<brief reasoning>"
}}"""


# ---------------------------------------------------------------------------
# Model API calls
# ---------------------------------------------------------------------------

def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def call_with_retry(fn, retries: int = 3, base_delay: float = 2.0):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            console.print(f"[yellow]Retry {attempt+1}/{retries}: {e}. Waiting {delay:.1f}s[/yellow]")
            time.sleep(delay)


def call_model(model_cfg: dict, prompt: str) -> str:
    api = model_cfg["api"]
    model_id = model_cfg["model_id"]

    if api == "anthropic":
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        def _call():
            msg = client.messages.create(
                model=model_id, max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text

    elif api == "openai":
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        def _call():
            resp = client.chat.completions.create(
                model=model_id, max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content

    elif api == "google":
        def _call():
            client = google_genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
            return client.models.generate_content(model=model_id, contents=prompt).text

    else:
        raise ValueError(f"Unknown API: {api}")

    return call_with_retry(_call)


def make_mock_response(question) -> dict:
    v = question.current_value if question.current_value > 0 else 200.0
    spread = v * 0.05
    point = round(v * (1 + random.uniform(-0.03, 0.03)), 4)
    return {
        "point_estimate": point,
        "50_ci": [round(point - spread * 0.5, 4), round(point + spread * 0.5, 4)],
        "80_ci": [round(point - spread, 4),        round(point + spread, 4)],
        "90_ci": [round(point - spread * 1.5, 4),  round(point + spread * 1.5, 4)],
        "reasoning": "Mock response for dry-run testing.",
    }


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

def collect_all(config: dict, dry_run: bool = False):
    from domains import generate_all_questions

    models = config["models"]
    pred_date = date.today()

    console.print(f"\n[bold]Generating questions for {pred_date}...[/bold]")
    questions = generate_all_questions(config, pred_date)
    console.print(f"[bold]Total: {len(questions)} questions × {len(models)} models[/bold]\n")

    if dry_run:
        console.print("[cyan]DRY RUN — using mock responses[/cyan]\n")

    for model_cfg in models:
        console.print(f"\n[bold blue]Model: {model_cfg['name']}[/bold blue]")
        for question in questions:
            filename = (
                PREDICTION_DIR
                / f"{model_cfg['name']}_{question.question_id}_{pred_date.isoformat()}.json"
            )
            if filename.exists():
                console.print(f"  [dim]SKIP[/dim] {question.question_id}")
                continue

            prompt = PROMPT_TEMPLATE.format(
                date=pred_date.isoformat(),
                context=question.context,
                question_text=question.question_text,
                unit=question.unit,
            )

            try:
                if dry_run:
                    parsed = make_mock_response(question)
                    raw = json.dumps(parsed)
                else:
                    raw = call_model(model_cfg, prompt)
                    parsed = parse_json_response(raw)

                record = {
                    "model": model_cfg["name"],
                    "model_id": model_cfg["model_id"],
                    "pred_date": pred_date.isoformat(),
                    "question": question.to_dict(),
                    "prediction": parsed,
                    "raw_response": raw if not dry_run else None,
                }
                filename.write_text(json.dumps(record, indent=2))
                console.print(f"  [green]OK[/green] {question.question_id}")

            except Exception as e:
                console.print(f"  [red]FAIL[/red] {question.question_id}: {e}")

            if not dry_run:
                time.sleep(0.3)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    collect_all(config, dry_run=args.dry_run)
