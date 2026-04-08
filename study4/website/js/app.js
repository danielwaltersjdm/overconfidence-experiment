/**
 * app.js — LLM Confidence Index Dashboard
 *
 * Reads rolling_index.json, time_series.json, items_list.json from ./data/.
 * Falls back to inline mock data if files are unavailable.
 * Supports filtering by sector and individual stock (on-demand loading).
 * Horizons discovered dynamically from the data (supports 1–30+ day horizons).
 */

"use strict";

// ── Model config ─────────────────────────────────────────────────────────────

const MODELS = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gpt4:   { label: "GPT-4",  color: "#059669" },
  gemini: { label: "Gemini", color: "#d97706" },
};
const MODEL_KEYS_DEFAULT = ["claude", "gpt4o", "gemini"];

const METRIC_CONFIG = {
  mu:          { label: "\u03bc (MEAD / MAD)", target: 1.0, min: 0, max: 2, fmt: v => v === null || isNaN(v) ? "\u2014" : v.toFixed(2) },
  accuracy:    { label: "Accuracy (normalized MAD)", target: null, min: 0, max: null, fmt: v => v === null || isNaN(v) ? "\u2014" : (v * 100).toFixed(2) + "%" },
  hit_rate_90: { label: "90% CI Hit Rate", target: 0.90, min: 0, max: 1, fmt: v => pct(v) },
};

// ── State ────────────────────────────────────────────────────────────────────

let rolling = null;
let series = null;
let itemsList = [];
let horizonsList = [];
let modelKeys = [];
let horizon = "1d";
let metric = "mu";
let chart = null;
let usingMock = false;

let filterSector = "all";
let filterStock = null;
let stockSeriesCache = {};

// ── Horizon helpers ──────────────────────────────────────────────────────────

function horizonDays(h) {
  const m = h.match(/^(\d+)/);
  return m ? parseInt(m[1], 10) : 1;
}

function horizonLabel(h) {
  const days = horizonDays(h);
  if (days === 1) return "1-Day";
  if (days === 7) return "1-Week";
  if (days === 30) return "1-Month";
  return days + "-Day";
}

function sortHorizons(arr) {
  return arr.slice().sort((a, b) => horizonDays(a) - horizonDays(b));
}

// ── Mock data ────────────────────────────────────────────────────────────────

function generateMockData() {
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 40);
  const startStr = startDate.toISOString().split("T")[0];
  const todayStr = today.toISOString().split("T")[0];

  const dates = [];
  const d = new Date(startDate);
  while (dates.length < 25) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(d.toISOString().split("T")[0]);
  }

  function noisySeries(base, len, spread) {
    const arr = []; let v = base;
    for (let i = 0; i < len; i++) {
      v += (Math.random() - 0.5) * spread;
      v = Math.max(0.1, Math.min(2.0, v));
      arr.push(Math.round(v * 1000) / 1000);
    }
    return arr;
  }

  const sectors = ["Technology", "Financials", "Healthcare", "Consumer Discretionary",
                   "Consumer Staples", "Industrials", "Energy", "Utilities"];
  const mockHorizons = ["1d", "2d", "3d", "6d", "7d", "14d", "18d", "20d", "21d", "22d", "30d"];
  const mockModels = ["claude", "gpt4", "gemini"];

  const mockItems = [
    {id:"AAPL",label:"Apple",sector:"Technology"},{id:"MSFT",label:"Microsoft",sector:"Technology"},
    {id:"NVDA",label:"NVIDIA",sector:"Technology"},{id:"GOOGL",label:"Alphabet A",sector:"Technology"},
    {id:"JPM",label:"JPMorgan Chase",sector:"Financials"},{id:"BAC",label:"Bank of America",sector:"Financials"},
    {id:"UNH",label:"UnitedHealth",sector:"Healthcare"},{id:"LLY",label:"Eli Lilly",sector:"Healthcare"},
    {id:"AMZN",label:"Amazon",sector:"Consumer Discretionary"},{id:"TSLA",label:"Tesla",sector:"Consumer Discretionary"},
    {id:"XOM",label:"Exxon Mobil",sector:"Energy"},{id:"CVX",label:"Chevron",sector:"Energy"},
  ];

  const baseMu  = { claude: 0.92, gpt4: 0.65, gemini: 0.80 };
  const baseAcc = { claude: 0.025, gpt4: 0.038, gemini: 0.030 };
  const baseHR  = { claude: 0.85, gpt4: 0.55, gemini: 0.72 };

  const rollingIndex = {
    generated_at: new Date().toISOString(), window_days: 30,
    study_start_date: startStr, data_through: todayStr,
    horizons_list: mockHorizons, _mock: true, models: {}
  };

  mockModels.forEach(m => {
    const hzData = {};
    mockHorizons.forEach(hz => {
      const hDays = horizonDays(hz);
      // Degrade calibration slightly with longer horizons
      const degradation = hDays * 0.003;
      const sectorData = {};
      sectors.forEach(sec => {
        const offset = (Math.random() - 0.5) * 0.15;
        sectorData[sec] = {
          n: 15 + Math.round(Math.random() * 30),
          mu: Math.round(Math.max(0.3, Math.min(1.8, baseMu[m] - degradation + offset)) * 1000) / 1000,
          accuracy: Math.round(Math.max(0.005, baseAcc[m] + degradation * 0.3 + (Math.random() - 0.5) * 0.01) * 10000) / 10000,
          hit_rate_90: Math.round(Math.max(0.3, Math.min(1.0, baseHR[m] - degradation + offset * 0.5)) * 1000) / 1000,
        };
      });
      const itemData = {};
      mockItems.forEach(it => {
        const offset = (Math.random() - 0.5) * 0.2;
        itemData[it.id] = {
          n: 3 + Math.round(Math.random() * 5),
          mu: Math.round(Math.max(0.2, Math.min(2.0, baseMu[m] - degradation + offset)) * 1000) / 1000,
          accuracy: Math.round(Math.max(0.003, baseAcc[m] + degradation * 0.3 + (Math.random() - 0.5) * 0.02) * 10000) / 10000,
          hit_rate_90: Math.round(Math.max(0.2, Math.min(1.0, baseHR[m] - degradation + offset * 0.4)) * 1000) / 1000,
        };
      });
      hzData[hz] = {
        status: "active", days_until_first: 0,
        n: dates.length * 50,
        mu: Math.round((baseMu[m] - degradation) * 1000) / 1000,
        accuracy: Math.round((baseAcc[m] + degradation * 0.3) * 10000) / 10000,
        hit_rate_90: Math.round((baseHR[m] - degradation) * 1000) / 1000,
        mean_ece: Math.round(Math.abs(0.90 - baseHR[m] + degradation) * 0.7 * 1000) / 1000,
        sectors: sectorData, items: itemData,
      };
    });
    rollingIndex.models[m] = {
      model_id: m === "claude" ? "claude-sonnet-4-20250514" : m === "gpt4" ? "gpt-4o" : "gemini-2.5-flash",
      horizons: hzData,
    };
  });

  const timeSeries = {
    generated_at: new Date().toISOString(), window_days: 30, _mock: true, horizons: {}
  };
  mockHorizons.forEach(hz => {
    const hDays = horizonDays(hz);
    const deg = hDays * 0.003;
    const hzSectors = {};
    sectors.forEach(sec => {
      hzSectors[sec] = { models: {} };
      mockModels.forEach(m => {
        hzSectors[sec].models[m] = {
          hit_rate_90: noisySeries(baseHR[m] - deg, dates.length, 0.1),
          mu: noisySeries(baseMu[m] - deg, dates.length, 0.12),
          accuracy: noisySeries(baseAcc[m] + deg * 0.3, dates.length, 0.01),
          n: dates.map(() => 3 + Math.round(Math.random() * 5)),
        };
      });
    });
    timeSeries.horizons[hz] = {
      status: "active", dates: dates,
      models: {},
      sectors: hzSectors,
    };
    mockModels.forEach(m => {
      timeSeries.horizons[hz].models[m] = {
        hit_rate_90: noisySeries(baseHR[m] - deg, dates.length, 0.06),
        mu: noisySeries(baseMu[m] - deg, dates.length, 0.08),
        accuracy: noisySeries(baseAcc[m] + deg * 0.3, dates.length, 0.008),
        n: dates.map((_, i) => 20 * (i + 1)),
      };
    });
  });

  return { rollingIndex, timeSeries, itemsList: mockItems };
}

function generateMockItemSeries(ticker) {
  const today = new Date();
  const dates = [];
  const d = new Date(today);
  d.setDate(d.getDate() - 30);
  while (dates.length < 15) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(d.toISOString().split("T")[0]);
  }
  function ns(b,l,s){const a=[];let v=b;for(let i=0;i<l;i++){v+=(Math.random()-0.5)*s;v=Math.max(0.1,Math.min(2,v));a.push(Math.round(v*1000)/1000);}return a;}
  const hzs = {};
  horizonsList.forEach(hz => {
    hzs[hz] = { status:"active", dates, models:{} };
    modelKeys.forEach(m => {
      hzs[hz].models[m] = {
        hit_rate_90:ns(0.75,dates.length,0.15), mu:ns(0.85,dates.length,0.2),
        accuracy:ns(0.03,dates.length,0.015), n:dates.map(()=>1),
      };
    });
  });
  return { ticker, label: ticker, sector: "Unknown", horizons: hzs };
}

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
    series = ts;
    itemsList = Array.isArray(il) ? il : [];
    usingMock = false;
  } catch {
    const mock = generateMockData();
    rolling = mock.rollingIndex;
    series = mock.timeSeries;
    itemsList = mock.itemsList;
    usingMock = true;
  }

  // Discover models and horizons from data
  modelKeys = Object.keys(rolling.models || {});
  if (modelKeys.length === 0) modelKeys = MODEL_KEYS_DEFAULT;

  horizonsList = rolling.horizons_list
    ? sortHorizons(rolling.horizons_list)
    : sortHorizons(Object.keys(series?.horizons || {}));
  if (horizonsList.length === 0) horizonsList = ["1d"];
  horizon = horizonsList[0];

  populateHorizonSelect();
  populateSectorFilter();
  initStockSearch();
  updateStatus();
  render();
  bindHorizonSelect();
  bindMetricTabs();
  bindFilters();
});

// ── Data loading ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  if (!data || typeof data !== "object") throw new Error("Empty");
  return data;
}

async function fetchItemSeries(ticker) {
  if (stockSeriesCache[ticker]) return stockSeriesCache[ticker];
  try {
    const data = await fetchJSON("./data/items/" + ticker + ".json");
    stockSeriesCache[ticker] = data;
    return data;
  } catch {
    const mock = generateMockItemSeries(ticker);
    stockSeriesCache[ticker] = mock;
    return mock;
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
  if (usingMock) { setStatus("amber", "Showing sample data \u2014 live data not yet available"); return; }
  const gen = rolling?.generated_at;
  if (!gen) { setStatus("red", "Data unavailable"); return; }
  const hours = (Date.now() - new Date(gen).getTime()) / (1000 * 60 * 60);
  if (hours < 26)      setStatus("green", "Updated " + fmtDate(gen));
  else if (hours < 72) setStatus("amber", "Updated " + fmtDate(gen));
  else                 setStatus("red", "Last update: " + fmtDate(gen));
}

// ── Horizon selector ─────────────────────────────────────────────────────────

function populateHorizonSelect() {
  const sel = document.getElementById("horizon-select");
  if (!sel) return;
  sel.innerHTML = "";
  horizonsList.forEach(h => {
    const opt = document.createElement("option");
    opt.value = h;
    opt.textContent = horizonLabel(h);
    sel.appendChild(opt);
  });
  sel.value = horizon;
}

function bindHorizonSelect() {
  const sel = document.getElementById("horizon-select");
  if (!sel) return;
  sel.addEventListener("change", () => {
    horizon = sel.value;
    renderForHorizon();
  });
}

// ── Filters ──────────────────────────────────────────────────────────────────

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

async function onFilterChange() {
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

function renderForHorizon() {
  renderCards();
  renderChart();
  renderDomainTable();
  document.getElementById("cards-horizon-label").textContent =
    horizonLabel(horizon).toLowerCase() + " horizon";
}

// ── Metric tabs ──────────────────────────────────────────────────────────────

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
    const cfg = MODELS[m] || { label: m, color: "#6b7280" };
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

// ── Chart.js error-bars plugin ───────────────────────────────────────────────

const errorBarPlugin = {
  id: "errorBars",
  afterDatasetsDraw(chart) {
    const ctx = chart.ctx;
    chart.data.datasets.forEach((dataset, i) => {
      if (!dataset.errorBars) return;
      const meta = chart.getDatasetMeta(i);
      if (meta.hidden) return;
      ctx.save();
      ctx.strokeStyle = dataset.borderColor || "#333";
      ctx.lineWidth = 1.5;
      const capW = 4;
      dataset.errorBars.forEach((eb, j) => {
        if (!eb || eb.plus == null || eb.minus == null) return;
        const pt = meta.data[j];
        if (!pt) return;
        const x = pt.x;
        const yTop = chart.scales.y.getPixelForValue(eb.plus);
        const yBot = chart.scales.y.getPixelForValue(eb.minus);
        // Vertical line
        ctx.beginPath();
        ctx.moveTo(x, yTop);
        ctx.lineTo(x, yBot);
        ctx.stroke();
        // Top cap
        ctx.beginPath();
        ctx.moveTo(x - capW, yTop);
        ctx.lineTo(x + capW, yTop);
        ctx.stroke();
        // Bottom cap
        ctx.beginPath();
        ctx.moveTo(x - capW, yBot);
        ctx.lineTo(x + capW, yBot);
        ctx.stroke();
      });
      ctx.restore();
    });
  }
};

// ── Horizon comparison chart ────────────────────────────────────────────────

function getHorizonData(modelKey, hz) {
  /** Get aggregate data for a model at a given horizon, respecting filters. */
  const hData = rolling?.models?.[modelKey]?.horizons?.[hz];
  if (!hData || hData.status !== "active") return null;
  if (filterStock) return hData.items?.[filterStock] || null;
  if (filterSector !== "all") return hData.sectors?.[filterSector] || null;
  return hData;
}

function renderChart() {
  const canvas = document.getElementById("main-chart");
  const rampup = document.getElementById("chart-rampup");
  if (!canvas || !rampup) return;

  // Check if any horizon has data
  const hasAnyData = horizonsList.some(hz =>
    modelKeys.some(m => {
      const d = getHorizonData(m, hz);
      return d && d.n > 0;
    })
  );

  if (!hasAnyData) {
    canvas.style.display = "none";
    rampup.style.display = "flex";
    rampup.innerHTML = `
      <div class="rampup-icon">\u23F3</div>
      <div class="rampup-title">Data unavailable</div>
      <div class="rampup-body">No resolved predictions yet. Check back soon.</div>`;
    return;
  }

  canvas.style.display = "";
  rampup.style.display = "none";

  const mcfg = METRIC_CONFIG[metric];
  const seKey = metric === "hit_rate_90" ? "hit_rate_90_se" : metric + "_se";
  const labels = horizonsList.map(h => horizonLabel(h));

  const datasets = modelKeys.map(m => {
    const cfg = MODELS[m] || { label: m, color: "#6b7280" };
    const values = [];
    const errors = [];
    const sampleSizes = [];

    horizonsList.forEach(hz => {
      const d = getHorizonData(m, hz);
      const val = d?.[metric] ?? NaN;
      const se = d?.[seKey] ?? null;
      const n = d?.n ?? 0;
      values.push(val !== null ? val : NaN);
      sampleSizes.push(n);
      if (se !== null && se !== undefined && !isNaN(val)) {
        errors.push({ plus: val + 1.96 * se, minus: val - 1.96 * se });
      } else {
        errors.push(null);
      }
    });

    return {
      label:           cfg.label,
      data:            values,
      borderColor:     cfg.color,
      backgroundColor: cfg.color + "30",
      borderWidth:     2.5,
      pointRadius:     5,
      pointHoverRadius: 7,
      pointBackgroundColor: cfg.color,
      tension:         0.2,
      spanGaps:        true,
      fill:            false,
      errorBars:       errors,
      _sampleSizes:    sampleSizes,
    };
  });

  // Target line
  if (mcfg.target !== null) {
    datasets.push({
      label:       "Target (" + (metric === "mu" ? "1.0" : "90%") + ")",
      data:        labels.map(() => mcfg.target),
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
    plugins: [errorBarPlugin],
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
          titleFont: { size: 12 }, bodyFont: { size: 12 },
          padding: 12, cornerRadius: 6,
          callbacks: {
            label: ctx => {
              const ds = ctx.dataset;
              const v = ctx.parsed.y;
              const valStr = isNaN(v) ? "\u2014" : mcfg.fmt(v);
              const n = ds._sampleSizes ? ds._sampleSizes[ctx.dataIndex] : null;
              const eb = ds.errorBars ? ds.errorBars[ctx.dataIndex] : null;
              let line = " " + ds.label + ": " + valStr;
              if (n) line += "  (n=" + n.toLocaleString() + ")";
              if (eb) line += "  [" + mcfg.fmt(eb.minus) + ", " + mcfg.fmt(eb.plus) + "]";
              return line;
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true, text: "Prediction Horizon",
            font: { size: 12, weight: "600" }, color: "#64748b",
          },
          ticks: { font: { size: 11 }, color: "#94a3b8" },
          grid: { display: false },
        },
        y: {
          min: mcfg.min,
          max: mcfg.max,
          ticks: {
            callback: v => mcfg.fmt(v),
            font: { size: 11 }, color: "#94a3b8",
            stepSize: metric === "mu" ? 0.2 : metric === "accuracy" ? undefined : 0.1,
          },
          grid: { color: "#f1f5f9" },
          title: {
            display: true, text: mcfg.label,
            font: { size: 12, weight: "600" }, color: "#64748b",
          },
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
    const cfg = MODELS[m] || { label: m, color: "#6b7280" };
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
        <span class="cell-val" style="color:${muColor(mu)}">${mu !== null && mu !== undefined ? mu.toFixed(2) : "\u2014"}</span>
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
  if (v === null || v === undefined || isNaN(v)) return "\u2014";
  return (v * 100).toFixed(1) + "%";
}

function muColor(mu) {
  if (mu === null || mu === undefined || isNaN(mu)) return "var(--muted)";
  if (mu >= 0.85 && mu <= 1.15) return "var(--good)";
  if ((mu >= 0.70 && mu < 0.85) || (mu > 1.15 && mu <= 1.30)) return "var(--warn)";
  return "var(--bad)";
}

function getMuBadge(mu) {
  if (mu === null || mu === undefined || isNaN(mu)) return { cls: "badge-none", text: "Building data" };
  if (mu >= 0.85 && mu <= 1.15) return { cls: "badge-good", text: "Well calibrated" };
  if (mu >= 0.70 && mu < 0.85) return { cls: "badge-warn", text: "Slightly overconfident" };
  if (mu < 0.70) return { cls: "badge-bad", text: "Overconfident" };
  if (mu > 1.15 && mu <= 1.30) return { cls: "badge-warn", text: "Slightly underconfident" };
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

// ── Mobile nav toggle ───────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector("header nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => { nav.classList.toggle("open"); });
  }
});
