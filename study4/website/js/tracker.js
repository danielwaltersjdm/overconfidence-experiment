/**
 * tracker.js — Study 4 Daily Calibration Tracker
 *
 * Reads time_series.json for the time-series chart (dates on x-axis),
 * rolling_index.json for current-snapshot model cards + sector table,
 * items_list.json for search/filter, and items/{TICKER}.json for
 * per-stock time series.
 */

"use strict";

// ── Model config ─────────────────────────────────────────────────────────────

const MODEL_DISPLAY = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gpt4:   { label: "GPT-4",  color: "#059669" },
  gemini: { label: "Gemini", color: "#d97706" },
};

const METRIC_CONFIG = {
  mu:          { label: "\u03bc (MEAD / MAD)", target: 1.0, fmt: v => v == null || isNaN(v) ? "\u2014" : v.toFixed(2) },
  accuracy:    { label: "Accuracy (norm. MAD)", target: null, fmt: v => v == null || isNaN(v) ? "\u2014" : (v * 100).toFixed(2) + "%" },
  hit_rate_90: { label: "90% CI Hit Rate", target: 0.90, fmt: v => v == null || isNaN(v) ? "\u2014" : (v * 100).toFixed(1) + "%" },
};

// ── State ────────────────────────────────────────────────────────────────────

let rolling = null;       // rolling_index.json
let timeSeries = null;    // time_series.json
let itemsList = [];       // items_list.json
let modelKeys = [];       // discovered from data
let horizon = "1d";
let metric = "mu";
let chart = null;

// Filter state
let filterSector = "all";
let filterStock = null;
let stockSeriesCache = {};

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  setStatus("amber", "Loading data\u2026");

  try {
    const [ri, ts, il] = await Promise.all([
      fetchJSON("./data/rolling_index.json"),
      fetchJSON("./data/time_series.json"),
      fetchJSON("./data/items_list.json"),
    ]);
    rolling = ri;
    timeSeries = ts;
    itemsList = il;
  } catch (err) {
    console.error("Failed to load data:", err);
    setStatus("red", "Failed to load data");
    return;
  }

  // Discover models from rolling index
  modelKeys = Object.keys(rolling.models || {});

  // Populate horizons from time_series
  populateHorizonSelect();
  populateSectorFilter();
  initStockSearch();
  updateStatus();
  updateTrackingStats();
  render();
  bindHorizonSelect();
  bindMetricTabs();
  bindFilters();
});

// ── Data loading ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  if (!data || typeof data !== "object") throw new Error("Empty");
  return data;
}

async function fetchStockSeries(ticker) {
  if (stockSeriesCache[ticker]) return stockSeriesCache[ticker];
  try {
    const data = await fetchJSON("./data/items/" + ticker + ".json");
    stockSeriesCache[ticker] = data;
    return data;
  } catch {
    return null;
  }
}

// ── Status bar ───────────────────────────────────────────────────────────────

function setStatus(color, text) {
  const dot = document.getElementById("status-dot");
  const txt = document.getElementById("status-text");
  if (dot) dot.className = "status-dot " + color;
  if (txt) txt.textContent = text;
}

function updateStatus() {
  const dt = rolling?.data_through;
  const start = rolling?.study_start_date;
  if (!dt) { setStatus("red", "Data unavailable"); return; }
  setStatus("green", "Data through " + dt + (start ? " \u00b7 tracking since " + start : ""));
}

function updateTrackingStats() {
  // Days tracked
  const hData = timeSeries?.horizons?.[horizon];
  const dates = hData?.dates || [];
  const el = document.getElementById("stat-days");
  if (el) el.textContent = dates.length > 0 ? dates.length : "\u2014";

  // Total predictions across all models
  let totalN = 0;
  for (const m of modelKeys) {
    for (const h of Object.keys(rolling?.models?.[m]?.horizons || {})) {
      const d = rolling.models[m].horizons[h];
      if (d?.n) totalN += d.n;
    }
  }
  const predEl = document.getElementById("stat-predictions");
  if (predEl) predEl.textContent = totalN > 0 ? totalN.toLocaleString() : "\u2014";
}

// ── Filters ──────────────────────────────────────────────────────────────────

function populateHorizonSelect() {
  const sel = document.getElementById("horizon-select");
  if (!sel) return;
  // Discover horizons from time_series
  const tsHorizons = Object.keys(timeSeries?.horizons || {});
  if (tsHorizons.length > 0) {
    sel.innerHTML = "";
    sortHorizons(tsHorizons).forEach(h => {
      const opt = document.createElement("option");
      opt.value = h;
      opt.textContent = horizonLabel(h);
      sel.appendChild(opt);
    });
    if (!tsHorizons.includes(horizon)) horizon = tsHorizons[0];
  }
  sel.value = horizon;
}

function populateSectorFilter() {
  const sel = document.getElementById("sector-select");
  if (!sel) return;
  const sectors = [...new Set(itemsList.map(it => it.sector))].sort();
  sectors.forEach(sec => {
    const opt = document.createElement("option");
    opt.value = sec;
    opt.textContent = sec;
    sel.appendChild(opt);
  });
}

function initStockSearch() {
  const input = document.getElementById("stock-search");
  const dropdown = document.getElementById("stock-dropdown");
  if (!input || !dropdown) return;

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (q.length < 1) { dropdown.style.display = "none"; return; }
    const matches = itemsList.filter(it =>
      it.id.toLowerCase().includes(q) || it.label.toLowerCase().includes(q)
    ).slice(0, 12);
    if (matches.length === 0) { dropdown.style.display = "none"; return; }
    dropdown.innerHTML = matches.map(it =>
      '<div class="stock-option" data-ticker="' + it.id + '">' +
        '<strong>' + it.id + '</strong> <span class="stock-option-label">' + it.label + '</span>' +
        '<span class="stock-option-sector">' + it.sector + '</span>' +
      '</div>'
    ).join("");
    dropdown.style.display = "block";
    dropdown.querySelectorAll(".stock-option").forEach(el => {
      el.addEventListener("click", () => selectStock(el.dataset.ticker));
    });
  });

  input.addEventListener("focus", () => {
    if (input.value.trim().length >= 1) input.dispatchEvent(new Event("input"));
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".stock-search-wrap")) dropdown.style.display = "none";
  });
}

function selectStock(ticker) {
  filterStock = ticker;
  filterSector = "all";
  const input = document.getElementById("stock-search");
  const dropdown = document.getElementById("stock-dropdown");
  const secSel = document.getElementById("sector-select");
  if (input) input.value = ticker;
  if (dropdown) dropdown.style.display = "none";
  if (secSel) secSel.value = "all";
  document.getElementById("filter-clear").style.display = "";
  onFilterChange();
}

function bindHorizonSelect() {
  const sel = document.getElementById("horizon-select");
  if (!sel) return;
  sel.addEventListener("change", () => {
    horizon = sel.value;
    updateChartHorizonLabel();
    updateTrackingStats();
    render();
  });
}

function bindMetricTabs() {
  document.querySelectorAll("#metric-tabs .mtab").forEach(btn => {
    btn.addEventListener("click", () => {
      metric = btn.dataset.metric;
      document.querySelectorAll("#metric-tabs .mtab").forEach(b => {
        b.classList.toggle("active", b.dataset.metric === metric);
      });
      renderChart();
    });
  });
}

function bindFilters() {
  const secSel = document.getElementById("sector-select");
  const clearBtn = document.getElementById("filter-clear");
  const input = document.getElementById("stock-search");

  if (secSel) {
    secSel.addEventListener("change", () => {
      filterSector = secSel.value;
      filterStock = null;
      if (input) input.value = "";
      clearBtn.style.display = filterSector !== "all" ? "" : "none";
      onFilterChange();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      filterSector = "all";
      filterStock = null;
      if (secSel) secSel.value = "all";
      if (input) input.value = "";
      clearBtn.style.display = "none";
      onFilterChange();
    });
  }
}

function onFilterChange() {
  updateFilterLabel();
  renderCards();
  renderDomainTable();
  // For stock filter, load per-stock series; for sector, use time_series sectors
  renderChart();
}

function updateFilterLabel() {
  const el = document.getElementById("cards-filter-label");
  if (!el) return;
  if (filterStock) el.textContent = filterStock;
  else if (filterSector !== "all") el.textContent = filterSector;
  else el.textContent = "all stocks";
}

function updateChartHorizonLabel() {
  const el = document.getElementById("chart-horizon-label");
  if (el) el.textContent = horizonLabel(horizon);
}

// ── Render orchestration ─────────────────────────────────────────────────────

function render() {
  renderCards();
  renderChart();
  renderDomainTable();
  updateFilterLabel();
  updateChartHorizonLabel();
}

// ── Model cards (from rolling_index) ─────────────────────────────────────────

function getCardData(modelKey) {
  const hData = rolling?.models?.[modelKey]?.horizons?.[horizon];
  if (!hData || hData.status !== "active") return null;
  if (filterStock) return hData.items?.[filterStock] || null;
  if (filterSector !== "all") return hData.sectors?.[filterSector] || null;
  return hData;
}

function renderCards() {
  const container = document.getElementById("model-cards");
  if (!container) return;

  container.innerHTML = modelKeys.map(m => {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    const d = getCardData(m);
    const mu = d?.mu ?? null;
    const acc = d?.accuracy ?? null;
    const hr90 = d?.hit_rate_90 ?? null;
    const n = d?.n ?? null;
    const badge = getMuBadge(mu);

    const detailHtml = d ? `
      <div class="card-detail">
        <span>Accuracy: <strong>${acc !== null ? (acc * 100).toFixed(2) + "%" : "\u2014"}</strong></span>
        <span>90% CI: <strong>${pct(hr90)}</strong></span>
        <span>n = <strong>${n !== null ? n.toLocaleString() : "\u2014"}</strong></span>
      </div>` : "";

    return `
      <div class="card ${m}">
        <div class="card-name">${cfg.label}</div>
        <div class="card-value" style="color:${muColor(mu)}">${mu !== null ? mu.toFixed(2) : "\u2014"}</div>
        <div class="card-label">\u03bc (meta-knowledge)</div>
        <span class="badge ${badge.cls}">${badge.text}</span>
        ${detailHtml}
      </div>`;
  }).join("");
}

// ── Time series chart (dates on x-axis) ──────────────────────────────────────

function getTimeSeriesData() {
  // Returns { dates: [...], models: { modelKey: { metric: [...] } } }
  // Respects sector/stock filter

  if (filterStock) {
    // Need per-stock data — check cache or return null (will be loaded async)
    const cached = stockSeriesCache[filterStock];
    if (!cached) return null;
    const hData = cached.horizons?.[horizon];
    if (!hData || hData.status !== "active") return null;
    return { dates: hData.dates || [], models: hData.models || {} };
  }

  if (filterSector !== "all") {
    // Use sector data from time_series.json
    const hData = timeSeries?.horizons?.[horizon];
    if (!hData) return null;
    const secData = hData.sectors?.[filterSector];
    if (!secData) return null;
    return { dates: hData.dates || [], models: secData.models || {} };
  }

  // Aggregate (all stocks)
  const hData = timeSeries?.horizons?.[horizon];
  if (!hData) return null;
  return { dates: hData.dates || [], models: hData.models || {} };
}

async function renderChart() {
  const canvas = document.getElementById("main-chart");
  const rampup = document.getElementById("chart-rampup");
  if (!canvas) return;

  // If filtering by stock, load data first
  if (filterStock && !stockSeriesCache[filterStock]) {
    canvas.style.display = "none";
    if (rampup) {
      rampup.style.display = "flex";
      rampup.innerHTML = '<div class="rampup-icon">\u23F3</div><div class="rampup-title">Loading stock data\u2026</div>';
    }
    const data = await fetchStockSeries(filterStock);
    if (!data) {
      if (rampup) {
        rampup.innerHTML = '<div class="rampup-icon">\u274C</div><div class="rampup-title">No data for ' + filterStock + '</div>';
      }
      return;
    }
  }

  const tsData = getTimeSeriesData();
  const mcfg = METRIC_CONFIG[metric];

  if (!tsData || !tsData.dates || tsData.dates.length === 0) {
    canvas.style.display = "none";
    if (rampup) {
      rampup.style.display = "flex";
      rampup.innerHTML = `
        <div class="rampup-icon">\u23F3</div>
        <div class="rampup-title">Collecting data</div>
        <div class="rampup-body">
          The daily tracker needs at least 30 days of predictions before
          rolling metrics can be computed. Check back soon.
        </div>`;
    }
    return;
  }

  canvas.style.display = "";
  if (rampup) rampup.style.display = "none";

  const dates = tsData.dates;
  const datasets = [];

  for (const m of modelKeys) {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    const mData = tsData.models?.[m];
    if (!mData) continue;

    const metricArr = mData[metric] || [];
    const nArr = mData.n || [];

    // Build {x, y} points, skipping nulls
    const points = [];
    for (let i = 0; i < dates.length; i++) {
      const v = metricArr[i];
      if (v != null && !isNaN(v)) {
        points.push({ x: dates[i], y: v });
      }
    }

    if (points.length === 0) continue;

    datasets.push({
      label: cfg.label,
      data: points,
      borderColor: cfg.color,
      backgroundColor: cfg.color + "20",
      borderWidth: 2,
      pointRadius: dates.length > 60 ? 0 : 3,
      pointHoverRadius: 5,
      tension: 0.3,
      fill: false,
      _nValues: nArr,
      _dates: dates,
    });
  }

  // Target line
  if (mcfg.target !== null && datasets.length > 0) {
    datasets.push({
      label: "Target (" + mcfg.fmt(mcfg.target) + ")",
      data: [{ x: dates[0], y: mcfg.target }, { x: dates[dates.length - 1], y: mcfg.target }],
      borderColor: "#dc2626",
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      fill: false,
    });
  }

  if (chart) chart.destroy();

  chart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "top",
          labels: { usePointStyle: true, pointStyle: "circle", padding: 16, font: { size: 12 } },
        },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.92)",
          titleFont: { size: 13 },
          bodyFont: { size: 12 },
          padding: 12,
          cornerRadius: 6,
          callbacks: {
            title: ctx => {
              const d = ctx[0]?.parsed?.x;
              if (!d) return "";
              try {
                return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
              } catch { return String(d); }
            },
            label: ctx => {
              const ds = ctx.dataset;
              const v = ctx.parsed.y;
              const fmtV = isNaN(v) ? "\u2014" : mcfg.fmt(v);
              let line = " " + ds.label + ": " + fmtV;
              // Try to find n
              if (ds._nValues && ds._dates) {
                const dateStr = ctx.raw?.x;
                const idx = ds._dates.indexOf(dateStr);
                if (idx >= 0 && ds._nValues[idx] != null) {
                  line += "  (n=" + ds._nValues[idx].toLocaleString() + ")";
                }
              }
              return line;
            }
          }
        }
      },
      scales: {
        x: {
          type: "time",
          time: {
            unit: "day",
            tooltipFormat: "MMM d, yyyy",
            displayFormats: { day: "MMM d" },
          },
          title: {
            display: true,
            text: "Date",
            font: { size: 12, weight: "600" },
            color: "#64748b",
          },
          ticks: { font: { size: 11 }, color: "#94a3b8", maxTicksLimit: 15 },
          grid: { display: false },
        },
        y: {
          title: {
            display: true,
            text: mcfg.label,
            font: { size: 12, weight: "600" },
            color: "#64748b",
          },
          ticks: {
            callback: v => mcfg.fmt(v),
            font: { size: 11 },
            color: "#94a3b8",
          },
          grid: { color: "#f1f5f9" },
        },
      },
    },
  });
}

// ── Sector table ─────────────────────────────────────────────────────────────

function renderDomainTable() {
  const container = document.getElementById("domain-table");
  if (!container) return;

  const hasData = modelKeys.some(
    m => rolling?.models?.[m]?.horizons?.[horizon]?.status === "active"
  );

  if (!hasData) {
    container.innerHTML = `
      <div style="padding:2.5rem 1rem;text-align:center;color:var(--muted);font-size:0.9rem">
        Sector breakdown unavailable for ${horizonLabel(horizon)} horizon.
      </div>`;
    return;
  }

  const sectorSet = new Set();
  modelKeys.forEach(m => {
    const secs = rolling?.models?.[m]?.horizons?.[horizon]?.sectors;
    if (secs) Object.keys(secs).forEach(s => sectorSet.add(s));
  });
  const sectors = Array.from(sectorSet).sort();

  const headerCells = modelKeys.map(m => {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    return `<th style="color:${cfg.color}">${cfg.label}</th>`;
  }).join("");

  const rows = sectors.map(sec => {
    const cells = modelKeys.map(m => {
      const d = rolling?.models?.[m]?.horizons?.[horizon]?.sectors?.[sec];
      if (!d || d.n === 0) {
        return `<td><span class="cell-val" style="color:var(--muted)">\u2014</span></td>`;
      }
      const mu = d.mu;
      return `<td>
        <span class="cell-val" style="color:${muColor(mu)}">${mu != null ? mu.toFixed(2) : "\u2014"}</span>
        <span class="cell-n">n=${d.n}</span>
      </td>`;
    }).join("");
    return `<tr><td><strong>${sec}</strong></td>${cells}</tr>`;
  }).join("");

  container.innerHTML = `
    <table>
      <thead><tr><th>Sector</th>${headerCells}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function sortHorizons(arr) {
  return arr.sort((a, b) => horizonDays(a) - horizonDays(b));
}

function horizonDays(h) {
  h = h.toLowerCase();
  if (h.endsWith("d")) return parseInt(h);
  if (h.endsWith("w")) return parseInt(h) * 7;
  if (h.endsWith("m")) return parseInt(h) * 30;
  return 9999;
}

function horizonLabel(h) {
  const d = horizonDays(h);
  if (d === 1) return "1-Day";
  if (d < 7) return d + "-Day";
  if (d === 7) return "1-Week";
  if (d < 30) return d + "-Day";
  if (d === 30) return "1-Month";
  return h;
}

function pct(v) {
  if (v == null || isNaN(v)) return "\u2014";
  return (v * 100).toFixed(1) + "%";
}

function muColor(mu) {
  if (mu == null || isNaN(mu)) return "var(--muted)";
  if (mu >= 0.85 && mu <= 1.15) return "var(--good)";
  if ((mu >= 0.70 && mu < 0.85) || (mu > 1.15 && mu <= 1.30)) return "var(--warn)";
  return "var(--bad)";
}

function getMuBadge(mu) {
  if (mu == null || isNaN(mu)) return { cls: "badge-none", text: "No data" };
  if (mu >= 0.85 && mu <= 1.15) return { cls: "badge-good", text: "Well calibrated" };
  if (mu >= 0.70 && mu < 0.85) return { cls: "badge-warn", text: "Slightly overconfident" };
  if (mu < 0.70) return { cls: "badge-bad", text: "Overconfident" };
  if (mu > 1.15 && mu <= 1.30) return { cls: "badge-warn", text: "Slightly underconfident" };
  return { cls: "badge-bad", text: "Underconfident" };
}
