# Filesystem Snapshot — 2026-04-06

```
overconfidence-experiment/
├── CLAUDE.md
├── STATE.md
├── voice_typing.ahk
│
├── study1/                          # Complete — 1-day equity predictions
│   ├── overconfidence_report.md
│   ├── predictions/                 # 300 JSON files (20 tickers × 3 models × 5 runs)
│   └── results/                     # scored.csv, summary.csv, 7 PNG charts
│
├── study2/                          # Complete — multi-horizon equity predictions
│   ├── collect_predictions.py
│   ├── fetch_actuals.py
│   ├── score.py
│   ├── visualize.py
│   ├── run_experiment.py
│   ├── report.py
│   ├── config.yaml
│   ├── requirements.txt
│   ├── overconfidence_report.md
│   └── data/
│       ├── predictions/             # 25,492 JSON files (100 tickers × 9 horizons × 3 models × 5 runs)
│       └── results/                 # scored.csv, summary.csv, 8 PNG charts
│
├── study3/                          # Complete — multi-domain, single horizon
│   ├── collect_predictions.py
│   ├── fetch_actuals.py
│   ├── score.py
│   ├── visualize.py
│   ├── run_experiment.py
│   ├── report.py
│   ├── build_ms.py / build_pdf.py   # Legacy fpdf2 paper generators
│   ├── config.yaml
│   ├── paper.tex / references.bib / paper.log
│   ├── paper_ms.pdf / paper_pnas.pdf / paper_v4.pdf
│   ├── overconfidence_report.md
│   ├── domains/                     # Domain modules: stocks, crypto, forex, weather, commodities, nba
│   └── data/
│       ├── predictions/             # 477 JSON files (6 domains × 3 models)
│       └── results/                 # scored.csv, summary.csv, 4 PNG charts
│
├── study4/                          # In Progress — longitudinal live tracking
│   ├── collect_predictions.py
│   ├── fetch_actuals.py
│   ├── score.py
│   ├── export_data.py
│   ├── config.yaml
│   ├── requirements.txt
│   ├── README.md
│   ├── PROCEDURE.md
│   ├── data/
│   │   ├── predictions/             # 120 JSON files (Day 1 only: 2026-04-03)
│   │   ├── actuals/                 # Empty — no actuals fetched yet
│   │   └── results/                 # Empty — no scoring yet
│   ├── logs/                        # Empty
│   └── website/
│       ├── index.html / about.html
│       ├── css/styles.css
│       ├── js/app.js
│       └── data/                    # Empty — no exports yet
│
├── paper/                           # Canonical LaTeX paper (PNAS format)
│   ├── main.tex                     # PNAS format — current canonical source
│   ├── main_pre_PNAS_style.tex      # MS/INFORMS backup
│   ├── pnas-new.cls / pnas-new.bst / pnasresearcharticle.sty
│   ├── references.bib
│   ├── main.aux / main.bbl / main.blg / main.log / main.out / main.pdf
│   ├── overconfidence_pnas.pdf      # Compiled PNAS output
│   ├── overconfidence_ms.pdf        # Compiled MS/INFORMS output
│   ├── sections/
│   │   ├── introduction.tex
│   │   ├── study1.tex / study2.tex / study3.tex
│   │   ├── discussion.tex
│   │   ├── methods.tex / results.tex              # MS-format sections
│   │   └── *_pre_PNAS_style.tex                   # MS-format backups (4 files)
│   ├── figures/                     # Reserved (empty)
│   └── tables/                      # Reserved (empty)
│
├── papers/                          # Reference literature (10 PDFs + web_appendix.md)
│
├── scripts/
│   └── sync_to_osf.py              # OSF sync script (node hqavj)
│
└── sessions/
    ├── filesystem-2026-04-03.md
    ├── filesystem-2026-04-06.md     # This file
    ├── session-2026-03-31.md
    ├── session-2026-04-02.md
    └── session-2026-04-03.md
```
