"""
Generate visualizations: calibration curves (overall + per domain), ECE heatmap.
Reads data/results/scored.csv, saves PNGs to data/results/.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from rich.console import Console

console = Console(legacy_windows=False)

RESULTS_DIR   = Path("data/results")
SCORED_FILE   = RESULTS_DIR / "scored.csv"
CONFIDENCE_LEVELS = [50, 80, 90]
PALETTE = sns.color_palette("tab10")


def load_scored() -> pd.DataFrame:
    if not SCORED_FILE.exists():
        raise FileNotFoundError(f"{SCORED_FILE} not found. Run score.py first.")
    return pd.read_csv(SCORED_FILE)


# ---------------------------------------------------------------------------
# 1. Overall calibration curves (one panel per model)
# ---------------------------------------------------------------------------

def plot_calibration_curves(df: pd.DataFrame) -> Path:
    models  = sorted(df["model"].unique())
    domains = sorted(df["domain"].unique())
    fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 5), sharey=True)
    if len(models) == 1:
        axes = [axes]

    for ax, model in zip(axes, models):
        ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.4, label="Perfect")
        sub = df[df["model"] == model]

        # Overall (all domains)
        stated, empirical = [], []
        for level in CONFIDENCE_LEVELS:
            hits = sub[f"hit_{level}"].dropna()
            if len(hits):
                stated.append(level / 100)
                empirical.append(hits.mean())
        ax.plot(stated, empirical, "o-", color="black", linewidth=2.5,
                markersize=8, label="Overall", zorder=5)

        # Per domain
        for i, domain in enumerate(domains):
            grp = sub[sub["domain"] == domain]
            s, e = [], []
            for level in CONFIDENCE_LEVELS:
                hits = grp[f"hit_{level}"].dropna()
                if len(hits):
                    s.append(level / 100)
                    e.append(hits.mean())
            if s:
                ax.plot(s, e, "o--", color=PALETTE[i % len(PALETTE)],
                        alpha=0.7, linewidth=1, markersize=5, label=domain)

        ax.set_title(model, fontsize=12, fontweight="bold")
        ax.set_xlim(0.4, 1.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xlabel("Stated confidence", fontsize=10)
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        ax.legend(loc="upper left", fontsize=7)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Actual hit rate", fontsize=10)
    fig.suptitle("Calibration Curves by Model and Domain\n(below diagonal = overconfident)", fontsize=13)
    out = RESULTS_DIR / "calibration_curves.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 2. ECE heatmap: model × domain
# ---------------------------------------------------------------------------

def plot_ece_heatmap(df: pd.DataFrame) -> Path:
    rows = []
    for (model, domain), grp in df.groupby(["model", "domain"]):
        eces = []
        for level in CONFIDENCE_LEVELS:
            hits = grp[f"hit_{level}"].dropna()
            if len(hits):
                eces.append(abs(level / 100 - hits.mean()))
        rows.append({"model": model, "domain": domain, "mean_ece": np.mean(eces) if eces else np.nan})

    pivot = pd.DataFrame(rows).pivot(index="model", columns="domain", values="mean_ece")

    fig, ax = plt.subplots(figsize=(max(6, len(pivot.columns) * 1.4), max(3, len(pivot) + 1)))
    sns.heatmap(
        pivot, ax=ax, annot=True, fmt=".2f",
        cmap="RdYlGn_r", vmin=0, vmax=0.4,
        linewidths=0.5, cbar_kws={"label": "Mean ECE (lower = better)"},
    )
    ax.set_title("Expected Calibration Error by Model × Domain\n(lower = better calibrated)", fontsize=11)
    ax.set_xlabel("Domain")
    ax.set_ylabel("Model")
    out = RESULTS_DIR / "ece_heatmap.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 3. CI width distributions (% of current value), faceted by domain
# ---------------------------------------------------------------------------

def plot_ci_widths(df: pd.DataFrame) -> Path:
    domains = sorted(df["domain"].unique())
    models  = sorted(df["model"].unique())
    fig, axes = plt.subplots(len(domains), len(CONFIDENCE_LEVELS),
                             figsize=(4 * len(CONFIDENCE_LEVELS), 2.5 * len(domains)),
                             sharey=False)
    if len(domains) == 1:
        axes = [axes]

    for row_idx, domain in enumerate(domains):
        sub = df[(df["domain"] == domain) & (df["current_value"] > 0)]
        for col_idx, level in enumerate(CONFIDENCE_LEVELS):
            ax = axes[row_idx][col_idx]
            for i, model in enumerate(models):
                grp = sub[sub["model"] == model].copy()
                grp["pct_width"] = (grp[f"ci_{level}_high"] - grp[f"ci_{level}_low"]) / grp["current_value"] * 100
                valid = grp["pct_width"].dropna()
                if not valid.empty:
                    ax.hist(valid, bins=15, alpha=0.6, color=PALETTE[i % len(PALETTE)],
                            label=model, density=True)
            if row_idx == 0:
                ax.set_title(f"{level}% CI", fontsize=10)
            if col_idx == 0:
                ax.set_ylabel(domain, fontsize=9, rotation=0, ha="right", va="center")
            ax.set_xlabel("Width (% of ref)", fontsize=8)
            ax.grid(alpha=0.3)
            if row_idx == 0 and col_idx == len(CONFIDENCE_LEVELS) - 1:
                ax.legend(fontsize=7)

    fig.suptitle("CI Width Distributions by Domain and Level", fontsize=12, y=1.01)
    out = RESULTS_DIR / "ci_widths.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 4. Brier score bar chart (per domain × model)
# ---------------------------------------------------------------------------

def plot_brier_scores(df: pd.DataFrame) -> Path:
    domains = sorted(df["domain"].unique())
    models  = sorted(df["model"].unique())
    summary = (
        df.groupby(["domain", "model"])["brier_score"]
        .mean()
        .reset_index()
    )

    fig, axes = plt.subplots(1, len(domains), figsize=(3.5 * len(domains), 4), sharey=False)
    if len(domains) == 1:
        axes = [axes]

    for ax, domain in zip(axes, domains):
        sub = summary[summary["domain"] == domain]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(sub))]
        bars = ax.bar(sub["model"], sub["brier_score"], color=colors, edgecolor="white")
        for bar, val in zip(bars, sub["brier_score"]):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                        f"{val:.4f}", ha="center", va="bottom", fontsize=7)
        ax.set_title(domain, fontsize=10)
        ax.set_xlabel("")
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Mean Brier Score (lower = better)", fontsize=9)
    fig.suptitle("Point Estimate Accuracy by Domain", fontsize=12)
    out = RESULTS_DIR / "brier_scores.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


def visualize_all() -> list[Path]:
    df = load_scored()
    return [
        p for p in [
            plot_calibration_curves(df),
            plot_ece_heatmap(df),
            plot_brier_scores(df),
            plot_ci_widths(df),
        ]
        if p is not None
    ]


if __name__ == "__main__":
    visualize_all()
