/**
 * app.js — LLM Confidence Index Dashboard
 *
 * Reads rolling_index.json, items_list.json from ./data/.
 * Chart: all prediction horizons on x-axis with 95% CI error bars.
 * Cards + sector table: filterable by horizon, sector, stock.
 */

"use strict";

// ── Model config (static display props; models discovered from data) ────────

const MODEL_DISPLAY = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gpt4:   { label: "GPT-4",  color: "#059669" },
  gemini: { label: "Gemini", color: "#d97706" },
};

const METRIC_CONFIG = {
  mu:          { label: "\u03bc (MEAD / MAD)", seKey: "mu_se", target: 1.0, fmt: v => v == null || isNaN(v) ? "\u2014" : v.toFixed(2) },
  accuracy:    { label: "Accuracy (norm. MAD)", seKey: "accuracy_se", target: null, fmt: v => v == null || isNaN(v) ? "\u2014" : (v * 100).toFixed(2) + "%" },
  hit_rate_90: { label: "90% CI Hit Rate", seKey: "hit_rate_90_se", target: 0.90, fmt: v => v == null || isNaN(v) ? "\u2014" : (v * 100).toFixed(1) + "%" },
};

// ── State ────────────────────────────────────────────────────────────────────

let rolling = null;
let itemsList = [];
let modelKeys = [];     // discovered from data
let allHorizons = [];   // discovered from data, sorted short-to-long
let horizon = null;     // selected horizon for cards/table
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
    const [ri, il] = await Promise.all([
      fetchJSON("./data/study2/rolling_index.json"),
      fetchJSON("./data/study2/items_list.json"),
    ]);
    rolling = ri;
    itemsList = il;
  } catch (err) {
    console.error("Failed to load data:", err);
    setStatus("red", "Failed to load data");
    return;
  }

  // Discover models + horizons from data
  modelKeys = Object.keys(rolling.models || {});
  allHorizons = rolling.horizons || discoverHorizons();
  horizon = allHorizons[0] || "1d";

  populateHorizonSelect();
  populateSectorFilter();
  initStockSearch();
  updateStatus();
  render();
  bindHorizonSelect();
  bindMetricTabs();
  bindFilters();
});

function discoverHorizons() {
  const hSet = new Set();
  for (const m of Object.values(rolling.models || {})) {
    for (const h of Object.keys(m.horizons || {})) {
      if (m.horizons[h].status === "active") hSet.add(h);
    }
  }
  return sortHorizons([...hSet]);
}

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

// ── Data loading ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  if (!data || typeof data !== "object") throw new Error("Empty");
  return data;
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
  if (!dt) { setStatus("red", "Data unavailable"); return; }
  setStatus("green", "Data through " + dt);
}

// ── Filters ──────────────────────────────────────────────────────────────────

function populateHorizonSelect() {
  const sel = document.getElementById("horizon-select");
  if (!sel) return;
  sel.innerHTML = "";
  allHorizons.forEach(h => {
    const opt = document.createElement("option");
    opt.value = h;
    opt.textContent = horizonLabel(h);
    sel.appendChild(opt);
  });
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
    renderCards();
    renderDomainTable();
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
  renderChart();
}

function updateFilterLabel() {
  const el = document.getElementById("cards-filter-label");
  if (!el) return;
  if (filterStock) el.textContent = filterStock;
  else if (filterSector !== "all") el.textContent = filterSector;
  else el.textContent = "all stocks";
}

// ── Render orchestration ─────────────────────────────────────────────────────

function render() {
  renderCards();
  renderChart();
  renderDomainTable();
  updateFilterLabel();
}

// ── Model cards ──────────────────────────────────────────────────────────────

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
    const badge = getHitRateBadge(hr90);

    const detailHtml = d ? `
      <div class="card-detail">
        <span>\u03bc: <strong>${mu !== null ? mu.toFixed(2) : "\u2014"}</strong></span>
        <span>Accuracy: <strong>${acc !== null ? (acc * 100).toFixed(2) + "%" : "\u2014"}</strong></span>
        <span>n = <strong>${n !== null ? n.toLocaleString() : "\u2014"}</strong></span>
      </div>` : "";

    return `
      <div class="card ${m}">
        <div class="card-name">${cfg.label}</div>
        <div class="card-value" style="color:${hitRateColor(hr90)}">${pct(hr90)}</div>
        <div class="card-label">90% CI hit rate</div>
        <span class="badge ${badge.cls}">${badge.text}</span>
        ${detailHtml}
      </div>`;
  }).join("");
}

// ── Chart: all horizons on x-axis with error bars ───────────────────────────

// Custom Chart.js plugin for vertical error bars
const errorBarPlugin = {
  id: "errorBars",
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((ds, dsIdx) => {
      if (!ds._errorBars) return;
      const meta = chart.getDatasetMeta(dsIdx);
      ds._errorBars.forEach((eb, i) => {
        if (!eb || eb.lo == null || eb.hi == null) return;
        const pt = meta.data[i];
        if (!pt) return;
        const x = pt.x;
        const yScale = chart.scales.y;
        const yLo = yScale.getPixelForValue(eb.lo);
        const yHi = yScale.getPixelForValue(eb.hi);
        const capW = 4;
        ctx.save();
        ctx.strokeStyle = ds.borderColor || "#666";
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.6;
        // Vertical line
        ctx.beginPath();
        ctx.moveTo(x, yLo);
        ctx.lineTo(x, yHi);
        ctx.stroke();
        // Bottom cap
        ctx.beginPath();
        ctx.moveTo(x - capW, yLo);
        ctx.lineTo(x + capW, yLo);
        ctx.stroke();
        // Top cap
        ctx.beginPath();
        ctx.moveTo(x - capW, yHi);
        ctx.lineTo(x + capW, yHi);
        ctx.stroke();
        ctx.restore();
      });
    });
  }
};
Chart.register(errorBarPlugin);

function getHorizonData(modelKey, h) {
  const hData = rolling?.models?.[modelKey]?.horizons?.[h];
  if (!hData || hData.status !== "active") return null;
  if (filterStock) return hData.items?.[filterStock] || null;
  if (filterSector !== "all") return hData.sectors?.[filterSector] || null;
  return hData;
}

function renderChart() {
  const canvas = document.getElementById("main-chart");
  const rampup = document.getElementById("chart-rampup");
  if (!canvas) return;

  const mcfg = METRIC_CONFIG[metric];
  const labels = allHorizons.map(h => horizonLabel(h));

  // Check if any data at all
  let anyData = false;
  for (const m of modelKeys) {
    for (const h of allHorizons) {
      if (getHorizonData(m, h)) { anyData = true; break; }
    }
    if (anyData) break;
  }

  if (!anyData) {
    canvas.style.display = "none";
    if (rampup) {
      rampup.style.display = "flex";
      rampup.innerHTML = '<div class="rampup-icon">\u23F3</div><div class="rampup-title">No data available</div>';
    }
    return;
  }

  canvas.style.display = "";
  if (rampup) rampup.style.display = "none";

  const datasets = modelKeys.map(m => {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    const values = [];
    const errorBars = [];
    const nValues = [];

    allHorizons.forEach(h => {
      const d = getHorizonData(m, h);
      const val = d?.[metric] ?? null;
      values.push(val);

      // 95% CI error bars (1.96 * SE)
      const se = d?.[mcfg.seKey] ?? null;
      if (val != null && se != null) {
        errorBars.push({ lo: val - 1.96 * se, hi: val + 1.96 * se });
      } else {
        errorBars.push(null);
      }
      nValues.push(d?.n ?? null);
    });

    return {
      label:           cfg.label,
      data:            values.map(v => v != null ? v : NaN),
      borderColor:     cfg.color,
      backgroundColor: cfg.color + "30",
      borderWidth:     2.5,
      pointRadius:     5,
      pointHoverRadius: 7,
      tension:         0.3,
      spanGaps:        false,
      fill:            false,
      _errorBars:      errorBars,
      _nValues:        nValues,
    };
  });

  // Add target line
  if (mcfg.target !== null) {
    datasets.push({
      label:       "Target (" + mcfg.fmt(mcfg.target) + ")",
      data:        allHorizons.map(() => mcfg.target),
      borderColor: "#dc2626",
      borderDash:  [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 0,
      fill:        false,
    });
  }

  if (chart) chart.destroy();

  chart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { labels, datasets },
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
            title: ctx => ctx[0]?.label || "",
            label: ctx => {
              const ds = ctx.dataset;
              const v = ctx.parsed.y;
              const fmtV = isNaN(v) ? "\u2014" : mcfg.fmt(v);
              let line = " " + ds.label + ": " + fmtV;
              // Add n= and CI bounds
              const nArr = ds._nValues;
              const ebArr = ds._errorBars;
              if (nArr) {
                const n = nArr[ctx.dataIndex];
                if (n != null) line += "  (n=" + n.toLocaleString() + ")";
              }
              if (ebArr) {
                const eb = ebArr[ctx.dataIndex];
                if (eb) line += "\n   95% CI: [" + mcfg.fmt(eb.lo) + ", " + mcfg.fmt(eb.hi) + "]";
              }
              return line;
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Prediction Horizon",
            font: { size: 12, weight: "600" },
            color: "#64748b",
          },
          ticks: { font: { size: 11 }, color: "#94a3b8" },
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

function hitRateColor(hr) {
  if (hr == null || isNaN(hr)) return "var(--muted)";
  if (hr >= 0.85 && hr <= 0.95) return "var(--good)";
  if ((hr >= 0.75 && hr < 0.85) || (hr > 0.95 && hr <= 1.0)) return "var(--warn)";
  return "var(--bad)";
}

function getHitRateBadge(hr) {
  if (hr == null || isNaN(hr)) return { cls: "badge-none", text: "No data" };
  if (hr >= 0.85 && hr <= 0.95) return { cls: "badge-good", text: "Well calibrated" };
  if (hr >= 0.75 && hr < 0.85) return { cls: "badge-warn", text: "Slightly overconfident" };
  if (hr < 0.75) return { cls: "badge-bad", text: "Overconfident" };
  if (hr > 0.95) return { cls: "badge-warn", text: "Slightly underconfident" };
  return { cls: "badge-bad", text: "Underconfident" };
}

function fmtDate(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}
