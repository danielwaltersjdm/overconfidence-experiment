"""
Domain registry: generate questions and fetch actuals across all domains.
"""
from datetime import date

from rich.console import Console

from .base import Question
from . import commodities, crypto, forex, nba, stocks, weather

console = Console(legacy_windows=False)

DOMAIN_MODULES = {
    "stocks":      stocks,
    "crypto":      crypto,
    "weather":     weather,
    "nba":         nba,
    "forex":       forex,
    "commodities": commodities,
}


def generate_all_questions(config: dict, pred_date: date) -> list[Question]:
    questions = []
    for domain, module in DOMAIN_MODULES.items():
        domain_cfg = config.get("domains", {}).get(domain, {})
        if not domain_cfg.get("enabled", True):
            console.print(f"[dim]SKIP domain {domain} (disabled)[/dim]")
            continue
        try:
            qs = module.generate_questions(config, pred_date)
            console.print(f"  [cyan]{domain}[/cyan]: {len(qs)} questions")
            questions.extend(qs)
        except Exception as e:
            console.print(f"  [red]FAIL {domain}: {e}[/red]")
    return questions


def fetch_actual_for_question(question: Question) -> tuple[float | None, str | None]:
    module = DOMAIN_MODULES[question.domain]
    return module.fetch_actual(question)
