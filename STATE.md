# STATE.md — Current Project Status

_Last updated: 2026-04-03_

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

---

## In Progress

_Nothing currently blocked._

---

## Blocked / Incomplete

| Item | Status | Notes |
|------|--------|-------|
| Table 2 (Study 2) | Partial | Only 4 of 9 horizon rows present; remaining rows in `study2/data/results/summary.csv` |
| MS abstract | Placeholder | `main_pre_PNAS_style.tex` still has placeholder abstract; not actively edited |
| Journal submission | Not started | Both formats compiled; submission workflow not started |
| Study 4 launch | Not started | Pipeline built; set `config.yaml → study.start_date`, add GitHub secrets, deploy website |
| Longitudinal replication | Addressed by Study 4 | Live tracking study now built |

---

## Open Decisions

- **Journal target**: PNAS vs. Management Science — `main.tex` is now PNAS format; MS backup retained
- **`*_pre_PNAS_style.tex` backups**: keep as reference or delete once PNAS version is final
- **Study 4 website deployment**: Vercel vs. Netlify — either works; configure deploy root to `study4/website`
