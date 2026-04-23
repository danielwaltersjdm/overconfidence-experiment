# STATE.md — Current Project Status

_Last updated: 2026-04-21_

---

## Done

- **Study 1** — data collected, actuals fetched, scored, visualized
- **Study 2** — data collected, actuals fetched, scored, visualized; multi-horizon summary complete
- **Study 3** — data collected, actuals fetched, scored across 6 domains; MEAD/MAD analysis complete
- **fpdf2 papers** — `study3/paper_ms.pdf` and `study3/paper_pnas.pdf` generated (legacy)
- **MS/INFORMS LaTeX compile** — `paper/overconfidence_ms.pdf` compiled clean (4 pages)
- **PNAS LaTeX compile** — `paper/overconfidence_pnas.pdf` compiled clean (6 pages)
- **Abstract + significance statement** — written in PNAS `main.tex`
- **Study 4 pipeline** — scripts, GitHub Actions workflows, static website, README built; deployed
- **Study 4 deployment** — live on GitHub Pages at https://danielwaltersjdm.github.io/overconfidence-experiment/
- **Study 4 daily automation** — full chain runs automatically weekdays:
  Collect (16:30 UTC) → Score (18:00 UTC) → Export → Deploy Pages
- **Gemini 503 retries** — fixed (5 retries, 30s+ backoff for rate limits)
- **Delisted tickers** — removed (FI, HES, MMC) and replaced (NXPI, FICO) to keep 200 stocks
- **Website redesign** — new nav (Daily Forecast / Horizon Backtest / Cross-Domain / Methodology / Researcher), 90% CI hit rate as primary metric, error bars on all charts, researcher bio page

---

## In Progress

- **Study 4 data accumulation** — 1d horizon has 8+ trading days of data; 1w
  horizon activated Apr 15 (Apr 8 predictions matured); 1m horizon will
  activate ~May 8 when Apr 8 predictions reach target date
- **Longitudinal trends** — meaningful time-series patterns will emerge
  after ~4 weeks of data

---

## Blocked / Incomplete

| Item | Status | Notes |
|------|--------|-------|
| Table 2 (Study 2) | Partial | Only 4 of 9 horizon rows present; remaining rows in `study2/data/results/summary.csv` |
| MS abstract | Placeholder | `main_pre_PNAS_style.tex` still has placeholder abstract; not actively edited |
| Journal submission | Not started | Both formats compiled; submission workflow not started |
| 1m horizon data | Not yet available | First predictions mature ~May 8, 2026 |

---

## Open Decisions

- **Journal target**: PNAS vs. Management Science — `main.tex` is now PNAS format; MS backup retained
- **`*_pre_PNAS_style.tex` backups**: keep as reference or delete once PNAS version is final
- **Study 4 domain scope**: stocks-only for now; consider adding crypto/forex/weather to daily collection
- **Findings section on Methodology page**: add once a few more weeks of data accumulate
