"""
Generate visualizations: calibration curves, Brier score bar chart, per-ticker heatmap.
Reads data/results/scored.csv and saves PNGs to data/results/.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from rich.console import Console

console = Console(legacy_windows=False)

RESULTS_DIR = Path("data/results")
SCORED_FILE = RESULTS_DIR / "scored.csv"

CONFIDENCE_LEVELS = [50, 80, 90]
PALETTE = sns.color_palette("tab10")


def load_scored() -> pd.DataFrame:
    if not SCORED_FILE.exists():
        raise FileNotFoundError(f"Scored file not found: {SCORED_FILE}. Run score.py first.")
    return pd.read_csv(SCORED_FILE)


# ---------------------------------------------------------------------------
# 1. Calibration curves
# ---------------------------------------------------------------------------

def plot_calibration_curves(df: pd.DataFrame) -> Path:
    windows = sorted(df["window_days"].dropna().unique().astype(int)) if "window_days" in df.columns else [None]
    models = sorted(df["model"].unique())
    ncols = len(windows)
    fig, axes = plt.subplots(1, ncols, figsize=(5 * ncols, 5), sharey=True)
    if ncols == 1:
        axes = [axes]

    for ax, window in zip(axes, windows):
        sub = df[df["window_days"] == window] if window is not None else df
        ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Perfect", alpha=0.5)

        for i, model in enumerate(models):
            grp = sub[sub["model"] == model]
            stated, empirical = [], []
            for level in CONFIDENCE_LEVELS:
                hits = grp[f"hit_{level}"].dropna()
                if len(hits) == 0:
                    continue
                stated.append(level / 100.0)
                empirical.append(hits.mean())
            if not stated:
                continue
            color = PALETTE[i % len(PALETTE)]
            ax.plot(stated, empirical, "o-", color=color, label=model, linewidth=2, markersize=7)
            for s, e in zip(stated, empirical):
                ax.annotate(f"{e:.2f}", (s, e), textcoords="offset points", xytext=(5, -4),
                            fontsize=7, color=color)

        label = f"{int(window)}d window" if window is not None else "All"
        ax.set_title(label, fontsize=11)
        ax.set_xlim(0.4, 1.0)
        ax.set_ylim(0.0, 1.05)
        ax.set_xlabel("Stated confidence", fontsize=10)
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Actual hit rate", fontsize=10)
    fig.suptitle("Calibration Curves by Prediction Window\n(below diagonal = overconfident)", fontsize=13)
    out = RESULTS_DIR / "calibration_curves.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 2. Brier score bar chart
# ---------------------------------------------------------------------------

def plot_brier_scores(df: pd.DataFrame) -> Path:
    windows = sorted(df["window_days"].dropna().unique().astype(int)) if "window_days" in df.columns else [None]
    models = sorted(df["model"].unique())
    ncols = len(windows)
    fig, axes = plt.subplots(1, ncols, figsize=(4 * ncols, 4), sharey=False)
    if ncols == 1:
        axes = [axes]

    for ax, window in zip(axes, windows):
        sub = df[df["window_days"] == window] if window is not None else df
        summary = (
            sub.groupby("model")["brier_score"]
            .agg(mean="mean", sem=lambda x: x.std() / np.sqrt(len(x)))
            .reindex(models)
            .reset_index()
        )
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(summary))]
        bars = ax.bar(summary["model"], summary["mean"], yerr=summary["sem"],
                      color=colors, capsize=4, edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, summary["mean"]):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0001,
                        f"{val:.4f}", ha="center", va="bottom", fontsize=8)
        label = f"{int(window)}d" if window is not None else "All"
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Model", fontsize=9)
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Mean Brier Score (lower = better)", fontsize=10)
    fig.suptitle("Point Estimate Accuracy by Window", fontsize=12)
    out = RESULTS_DIR / "brier_scores.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 3. Per-ticker heatmap (hit rate at 80% CI)
# ---------------------------------------------------------------------------

def plot_ticker_heatmap(df: pd.DataFrame) -> Path:
    # Use the 80% CI hit rate as the primary signal
    pivot = (
        df.dropna(subset=["hit_80"])
        .groupby(["model", "ticker"])["hit_80"]
        .mean()
        .unstack(level="ticker")
    )

    if pivot.empty:
        console.print("[yellow]Not enough data for heatmap — skipping[/yellow]")
        return None

    fig, ax = plt.subplots(figsize=(max(6, len(pivot.columns) * 1.2), max(3, len(pivot) * 0.8 + 1.5)))
    sns.heatmap(
        pivot,
        ax=ax,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Hit rate (80% CI)"},
    )
    ax.set_title("Per-Ticker Hit Rate at 80% Confidence Interval\n(green = well-calibrated, red = overconfident)", fontsize=11)
    ax.set_xlabel("Ticker", fontsize=11)
    ax.set_ylabel("Model", fontsize=11)

    # Add a reference line at 0.80
    for j in range(len(pivot.columns)):
        for i in range(len(pivot.index)):
            val = pivot.iloc[i, j]
            if not np.isnan(val) and val < 0.60:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=False, edgecolor="red", lw=2))

    out = RESULTS_DIR / "ticker_heatmap.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 4. Confidence interval width histogram
# ---------------------------------------------------------------------------

def plot_ci_width_histogram(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, len(CONFIDENCE_LEVELS), figsize=(14, 4), sharey=False)
    models = sorted(df["model"].unique())

    for ax, level in zip(axes, CONFIDENCE_LEVELS):
        for i, model in enumerate(models):
            grp = df[df["model"] == model].copy()
            grp["width"] = grp[f"ci_{level}_high"] - grp[f"ci_{level}_low"]
            grp["pct_width"] = grp["width"] / grp["current_price"] * 100
            valid = grp["pct_width"].dropna()
            if valid.empty:
                continue
            ax.hist(valid, bins=15, alpha=0.6, color=PALETTE[i % len(PALETTE)], label=model, density=True)

        ax.set_title(f"{level}% CI Width\n(% of current price)", fontsize=10)
        ax.set_xlabel("Width (%)", fontsize=9)
        ax.set_ylabel("Density" if level == CONFIDENCE_LEVELS[0] else "", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    fig.suptitle("Distribution of Confidence Interval Widths by Model", fontsize=12, y=1.02)
    out = RESULTS_DIR / "ci_widths.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


# ---------------------------------------------------------------------------
# 5. Hit rate vs prediction horizon (line chart by model)
# ---------------------------------------------------------------------------

def plot_hit_rate_by_window(df: pd.DataFrame) -> Path:
    windows = sorted(df["window_days"].dropna().unique().astype(int))
    models = sorted(df["model"].unique())

    fig, axes = plt.subplots(1, len(CONFIDENCE_LEVELS), figsize=(15, 5), sharey=True)

    for ax, level in zip(axes, CONFIDENCE_LEVELS):
        col = f"hit_{level}"
        stated = level / 100.0

        # Dashed reference line at the stated confidence level
        ax.axhline(stated, color="black", linestyle="--", linewidth=1.2, alpha=0.6,
                   label=f"Ideal ({level}%)")

        for i, model in enumerate(models):
            hit_rates = []
            for w in windows:
                sub = df[(df["model"] == model) & (df["window_days"] == w)][col].dropna()
                hit_rates.append(sub.mean() if len(sub) > 0 else float("nan"))
            ax.plot(windows, hit_rates, "o-", color=PALETTE[i % len(PALETTE)],
                    label=model, linewidth=2, markersize=6)

        ax.set_title(f"{level}% CI", fontsize=12)
        ax.set_xlabel("Prediction window (days)", fontsize=10)
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
        ax.set_xticks(windows)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Empirical hit rate", fontsize=11)
    fig.suptitle(
        "Hit Rate vs Prediction Horizon by Model\n"
        "(dashed = ideal, below dashed = overconfident)",
        fontsize=13,
    )
    out = RESULTS_DIR / "hit_rate_by_window.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    console.print(f"[green]Saved[/green] {out}")
    return out


def visualize_all() -> list[Path]:
    df = load_scored()
    paths = []
    paths.append(plot_calibration_curves(df))
    paths.append(plot_brier_scores(df))
    paths.append(plot_ticker_heatmap(df))
    paths.append(plot_ci_width_histogram(df))
    paths.append(plot_hit_rate_by_window(df))
    return [p for p in paths if p is not None]


if __name__ == "__main__":
    visualize_all()
