"""
Multi-domain overconfidence experiment — main entry point.

Usage:
    python run_experiment.py collect [--dry-run]
    python run_experiment.py fetch
    python run_experiment.py score
    python run_experiment.py visualize
    python run_experiment.py report
    python run_experiment.py all [--dry-run]
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
    path = Path("config.yaml")
    if not path.exists():
        console.print("[red]config.yaml not found. Run from the v2/ directory.[/red]")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def main():
    parser = argparse.ArgumentParser(
        description="Multi-domain AI overconfidence experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Stages:
  collect   Prompt each model for predictions → data/predictions/
  fetch     Fetch actual outcomes → data/results/actuals.csv
  score     Compute calibration metrics → data/results/scored.csv + summary.csv
  visualize Generate charts → data/results/*.png
  report    Generate overconfidence_report.md
  all       collect → fetch → score → visualize → report
        """,
    )
    parser.add_argument(
        "mode",
        choices=["collect", "fetch", "score", "visualize", "report", "all"],
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Use mock responses instead of live API calls (collect only)")
    args = parser.parse_args()
    config = load_config()

    if args.mode in ("collect", "all"):
        console.print(Rule("[bold blue]COLLECT[/bold blue]"))
        from collect_predictions import collect_all
        collect_all(config, dry_run=args.dry_run)

    if args.mode in ("fetch", "all"):
        console.print(Rule("[bold blue]FETCH ACTUALS[/bold blue]"))
        from fetch_actuals import fetch_actuals
        fetch_actuals()

    if args.mode in ("score", "all"):
        console.print(Rule("[bold blue]SCORE[/bold blue]"))
        if args.mode == "score":
            from fetch_actuals import fetch_actuals
            fetch_actuals()
        from score import score
        score()

    if args.mode in ("visualize", "all"):
        console.print(Rule("[bold blue]VISUALIZE[/bold blue]"))
        from visualize import visualize_all
        visualize_all()

    if args.mode in ("report", "all"):
        console.print(Rule("[bold blue]REPORT[/bold blue]"))
        from report import generate_report
        generate_report()

    console.print(Rule("[bold green]Done[/bold green]"))


if __name__ == "__main__":
    main()
