# Filesystem Snapshot — 2026-04-03

## Top-Level

```
overconfidence-experiment/
├── CLAUDE.md
├── STATE.md
├── voice_typing.ahk
├── paper/
├── papers/
├── sessions/
├── study1/
├── study2/
├── study3/
└── __pycache__/
```

---

## `paper/`

```
paper/
├── main.tex                        # Canonical PNAS source
├── main_pre_PNAS_style.tex         # MS/INFORMS backup
├── overconfidence_pnas.pdf         # Primary compiled output (6 pages)
├── overconfidence_ms.pdf           # MS/INFORMS compiled output (4 pages)
├── main.pdf                        # Alias / leftover from compile
├── pnas-new.cls                    # Locally modified PNAS class
├── pnas-new.bst                    # PNAS bibliography style
├── pnasresearcharticle.sty         # Created locally (not from MiKTeX)
├── references.bib                  # 13 references
├── main.aux / main.bbl / main.blg / main.log / main.out   # Build artifacts
├── sections/
│   ├── introduction.tex
│   ├── study1.tex
│   ├── study2.tex
│   ├── study3.tex
│   ├── discussion.tex
│   ├── introduction_pre_PNAS_style.tex
│   ├── methods.tex / methods_pre_PNAS_style.tex
│   ├── results.tex / results_pre_PNAS_style.tex
│   └── discussion_pre_PNAS_style.tex
├── figures/                        # (empty / reserved)
└── tables/                         # (empty / reserved)
```

---

## `study1/`

```
study1/
├── predictions/          # 300 JSON files (20 tickers × 5 runs × 3 models)
├── results/
│   ├── scored.csv
│   ├── summary.csv
│   ├── actuals.csv
│   ├── calibration_curves.png
│   ├── 90ci_by_model.png / 90ci_same_scale.png
│   ├── all_ci_vs_actual.png
│   ├── brier_scores.png
│   ├── ci_widths.png
│   └── ticker_heatmap.png
└── overconfidence_report.md
```

---

## `study2/`

```
study2/
├── collect_predictions.py
├── fetch_actuals.py
├── score.py
├── visualize.py
├── report.py
├── run_experiment.py
├── config.yaml
├── requirements.txt
├── overconfidence_report.md
├── collect_claude.log / collect_resume.log
└── data/
    ├── predictions/      # Multi-horizon JSONs (≥4,700 per model)
    └── results/
        ├── scored.csv
        ├── summary.csv
        ├── actuals.csv
        ├── calibration_curves.png
        ├── hit_rate_by_window.png
        ├── 90ci_by_model.png / 90ci_same_scale.png
        ├── all_ci_vs_actual.png
        ├── brier_scores.png
        ├── ci_widths.png
        └── ticker_heatmap.png
```

---

## `study3/`

```
study3/
├── collect_predictions.py
├── fetch_actuals.py
├── score.py
├── visualize.py
├── report.py
├── run_experiment.py
├── build_ms.py           # fpdf2 → paper_ms.pdf (legacy)
├── build_pdf.py          # fpdf2 → paper_pnas.pdf (legacy)
├── config.yaml
├── paper.log / paper.tex / paper_ms.pdf / paper_pnas.pdf / paper_v4.pdf
├── references.bib
├── overconfidence_report.md
├── domains/
│   ├── __init__.py / base.py
│   ├── stocks.py / crypto.py / forex.py
│   ├── weather.py / commodities.py / nba.py
│   └── __pycache__/
└── data/
    ├── predictions/      # Multi-domain JSONs (68 resolved items)
    └── results/
        ├── scored.csv
        ├── summary.csv
        ├── actuals.csv
        ├── calibration_curves.png
        ├── brier_scores.png
        ├── ci_widths.png
        └── ece_heatmap.png
```

---

## `papers/` (Reference Literature)

```
papers/
├── EBSCO-FullText-03_24_2026.pdf
├── fox_erner_walters_decision_under_risk_2016.pdf
├── ho_walters_leadership_quarterly_2012.pdf
├── known_unknowns_management_science.pdf
├── scholten_walters_psychological_review_2024.pdf
├── tomaino_walters_consumer_psychology_2023.pdf
├── walters_debt_aversion_psychological_science_2016.pdf
├── walters_fernbach_pnas_2021.pdf
├── walters_hershfield_jcr_2020.pdf
├── walters_management_science_2023.pdf
└── web_appendix.md
```

---

## `sessions/`

```
sessions/
├── session-2026-03-31.md
├── session-2026-04-02.md
└── filesystem-2026-04-03.md    # this file
```
