"""
Main entry point for the overconfidence experiment.

Usage:
    python run_experiment.py collect [--dry-run]
    python run_experiment.py score
    python run_experiment.py report
    python run_experiment.py all [--dry-run]   # collect + score + report (score/report only if window closed)
"""

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.rule import Rule

load_dotenv()
console = Console(legacy_windows=False)


def load_config() -> dict:
    config_path = Path("config.yaml")
    if not config_path.exists():
        console.print("[red]config.yaml not found. Are you in the project root?[/red]")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def cmd_collect(config: dict, dry_run: bool, backtest: bool = False):
    console.print(Rule("[bold blue]COLLECT[/bold blue]"))
    from collect_predictions import collect_all
    collect_all(config, dry_run=dry_run, backtest=backtest)


def cmd_fetch(config: dict):
    console.print(Rule("[bold blue]FETCH ACTUALS[/bold blue]"))
    from fetch_actuals import fetch_actuals
    fetch_actuals(config)


def cmd_score(config: dict):
    console.print(Rule("[bold blue]SCORE[/bold blue]"))
    from score import score
    score(config)


def cmd_visualize():
    console.print(Rule("[bold blue]VISUALIZE[/bold blue]"))
    from visualize import visualize_all
    visualize_all()


def cmd_report(config: dict):
    console.print(Rule("[bold blue]REPORT[/bold blue]"))
    from report import generate_report
    generate_report(config)


def main():
    parser = argparse.ArgumentParser(
        description="AI overconfidence experiment on stock price predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  collect   Prompt each AI model and save raw predictions to data/predictions/
  fetch     Pull actual prices from yfinance for closed prediction windows
  score     Compute Brier scores, hit rates, and ECE; save to data/results/
  visualize Generate calibration curves, Brier bar chart, and heatmap PNGs
  report    Generate overconfidence_report.md
  all       Run collect → fetch → score → visualize → report in sequence
        """,
    )
    parser.add_argument(
        "mode",
        choices=["collect", "fetch", "score", "visualize", "report", "all"],
        help="Which stage to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use mock AI responses instead of live API calls (collect mode only)",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Use historical prices (~backtest_days ago) with date blinded from models",
    )
    args = parser.parse_args()

    config = load_config()

    if args.mode == "collect":
        cmd_collect(config, dry_run=args.dry_run, backtest=args.backtest)

    elif args.mode == "fetch":
        cmd_fetch(config)

    elif args.mode == "score":
        cmd_fetch(config)
        cmd_score(config)

    elif args.mode == "visualize":
        cmd_visualize()

    elif args.mode == "report":
        cmd_report(config)

    elif args.mode == "all":
        cmd_collect(config, dry_run=args.dry_run, backtest=args.backtest)
        cmd_fetch(config)
        cmd_score(config)
        cmd_visualize()
        cmd_report(config)

    console.print(Rule("[bold green]Done[/bold green]"))


if __name__ == "__main__":
    main()
