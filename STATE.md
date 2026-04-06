# STATE.md — Current Project Status

_Last updated: 2026-04-06_

---

## Done

- **Study 1** — data collected, actuals fetched, scored, visualized
- **Study 2** — data collected, actuals fetched, scored, visualized; multi-horizon summary complete
- **Study 3** — data collected, actuals fetched, scored across 6 domains; MEAD/MAD analysis complete
- **fpdf2 papers** — `study3/paper_ms.pdf` and `study3/paper_pnas.pdf` generated (legacy)
- **MS/INFORMS LaTeX compile** — `paper/overconfidence_ms.pdf` compiled clean (4 pages)
- **PNAS LaTeX compile** — `paper/overconfidence_pnas.pdf` compiled clean (6 pages)
- **Abstract** — written in PNAS `main.tex`
- **Significance statement** — written in PNAS `main.tex`
- **Study 4 pipeline** — all scripts, GitHub Actions workflows, static website, and README built (2026-04-03); not yet deployed or collecting data
- **Study 4 website** — production-ready static site built (2026-04-06): index.html dashboard with model cards, Chart.js time-series, domain table, explainer; about.html with full methodology; mock data fallback; mobile-responsive

---

## In Progress

- **Study 4 data gap**: Only Day 1 (2026-04-03) predictions exist. No April 4 collection — GitHub Actions may not be triggering. Diagnose before Monday.
- **Study 4 venv**: No Python venv exists at project root. Need to create and install `study4/requirements.txt` to run pipeline locally.
- **Study 4 deploy**: Website ready; deploy `study4/website/` to Vercel or Netlify

---

## Blocked / Incomplete

| Item | Status | Notes |
|------|--------|-------|
| Table 2 (Study 2) | Partial | Only 4 of 9 horizon rows present; remaining rows in `study2/data/results/summary.csv` |
| MS abstract | Placeholder | `main_pre_PNAS_style.tex` still has placeholder abstract; not actively edited |
| Journal submission | Not started | Both formats compiled; submission workflow not started |
| Study 4 data gap | Blocked | Only Day 1 data; GitHub Actions not collecting since April 3 |
| Study 4 deploy | Ready | Website built; needs Vercel/Netlify deployment |
| Study 4 venv | Missing | No local venv — can't run pipeline scripts locally |
| Longitudinal replication | Addressed by Study 4 | Live tracking study now built |

---

## Open Decisions

- **Journal target**: PNAS vs. Management Science — `main.tex` is now PNAS format; MS backup retained
- **`*_pre_PNAS_style.tex` backups**: keep as reference or delete once PNAS version is final
- **Study 4 website deployment**: Vercel vs. Netlify — either works; configure deploy root to `study4/website`
