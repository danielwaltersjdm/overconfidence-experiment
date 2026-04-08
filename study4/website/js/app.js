/**
 * app.js — LLM Confidence Index Dashboard
 *
 * Reads rolling_index.json, time_series.json, items_list.json from ./data/.
 * Falls back to inline mock data if files are unavailable.
 * Supports filtering by sector and individual stock (on-demand loading).
 */

"use strict";

// ── Model config ─────────────────────────────────────────────────────────────

const MODELS = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gemini: { label: "Gemini", color: "#d97706" },
};
const MODEL_KEYS = Object.keys(MODELS);

const METRIC_CONFIG = {
  mu:          { label: "\u03bc (MEAD / MAD)", target: 1.0, min: 0, max: 2, fmt: v => v === null || isNaN(v) ? "\u2014" : v.toFixed(2) },
  accuracy:    { label: "Accuracy (normalized MAD)", target: null, min: 0, max: null, fmt: v => v === null || isNaN(v) ? "\u2014" : (v * 100).toFixed(2) + "%" },
  hit_rate_90: { label: "90% CI Hit Rate", target: 0.90, min: 0, max: 1, fmt: v => pct(v) },
};

const HORIZON_LABELS = { "1d": "1-Day", "1w": "1-Week", "1m": "1-Month" };

// ── State ────────────────────────────────────────────────────────────────────

let rolling = null;
let series = null;
let itemsList = [];
let horizon = "1d";
let metric = "mu";
let chart = null;
let usingMock = false;

// Filter state
let filterSector = "all";
let filterStock = null;
let stockSeriesCache = {};

// ── Mock data ────────────────────────────────────────────────────────────────

function generateMockData() {
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 20);
  const startStr = startDate.toISOString().split("T")[0];
  const todayStr = today.toISOString().split("T")[0];

  const dates = [];
  const d = new Date(startDate);
  d.setDate(d.getDate() + 1);
  while (dates.length < 15) {
    if (d.getDay() !== 0 && d.getDay() !== 6) {
      dates.push(d.toISOString().split("T")[0]);
    }
    d.setDate(d.getDate() + 1);
  }

  function noisySeries(base, len, spread) {
    const arr = [];
    let v = base;
    for (let i = 0; i < len; i++) {
      v += (Math.random() - 0.5) * spread;
      v = Math.max(0.1, Math.min(2.0, v));
      arr.push(Math.round(v * 1000) / 1000);
    }
    return arr;
  }

  const sectors = ["Technology", "Financials", "Healthcare", "Consumer Discretionary",
                   "Consumer Staples", "Industrials", "Energy", "Utilities"];

  const mockItems = [
    {id:"AAPL",label:"Apple",sector:"Technology"},{id:"MSFT",label:"Microsoft",sector:"Technology"},
    {id:"NVDA",label:"NVIDIA",sector:"Technology"},{id:"GOOGL",label:"Alphabet A",sector:"Technology"},
    {id:"JPM",label:"JPMorgan Chase",sector:"Financials"},{id:"BAC",label:"Bank of America",sector:"Financials"},
    {id:"UNH",label:"UnitedHealth",sector:"Healthcare"},{id:"LLY",label:"Eli Lilly",sector:"Healthcare"},
    {id:"AMZN",label:"Amazon",sector:"Consumer Discretionary"},{id:"TSLA",label:"Tesla",sector:"Consumer Discretionary"},
    {id:"PG",label:"Procter & Gamble",sector:"Consumer Staples"},{id:"KO",label:"Coca-Cola",sector:"Consumer Staples"},
    {id:"CAT",label:"Caterpillar",sector:"Industrials"},{id:"HON",label:"Honeywell",sector:"Industrials"},
    {id:"XOM",label:"Exxon Mobil",sector:"Energy"},{id:"CVX",label:"Chevron",sector:"Energy"},
    {id:"NEE",label:"NextEra Energy",sector:"Utilities"},{id:"SO",label:"Southern Company",sector:"Utilities"},
  ];

  const baseMu  = { claude: 0.92, gpt4o: 0.65, gemini: 0.80 };
  const baseAcc = { claude: 0.025, gpt4o: 0.038, gemini: 0.030 };
  const baseHR  = { claude: 0.85, gpt4o: 0.55, gemini: 0.72 };

  const rollingIndex = {
    generated_at: new Date().toISOString(),
    window_days: 30,
    study_start_date: startStr,
    data_through: todayStr,
    _mock: true,
    models: {}
  };

  MODEL_KEYS.forEach(m => {
    const sectorData = {};
    sectors.forEach(sec => {
      const offset = (Math.random() - 0.5) * 0.15;
      sectorData[sec] = {
        n: 15 + Math.round(Math.random() * 30),
        mu: Math.round(Math.max(0.3, Math.min(1.8, baseMu[m] + offset)) * 1000) / 1000,
        accuracy: Math.round(Math.max(0.005, baseAcc[m] + (Math.random() - 0.5) * 0.015) * 10000) / 10000,
        hit_rate_90: Math.round(Math.max(0.3, Math.min(1.0, baseHR[m] + offset * 0.5)) * 1000) / 1000,
      };
    });

    const itemData = {};
    mockItems.forEach(it => {
      const offset = (Math.random() - 0.5) * 0.2;
      itemData[it.id] = {
        n: 10 + Math.round(Math.random() * 5),
        mu: Math.round(Math.max(0.2, Math.min(2.0, baseMu[m] + offset)) * 1000) / 1000,
        accuracy: Math.round(Math.max(0.003, baseAcc[m] + (Math.random() - 0.5) * 0.02) * 10000) / 10000,
        hit_rate_90: Math.round(Math.max(0.2, Math.min(1.0, baseHR[m] + offset * 0.4)) * 1000) / 1000,
      };
    });

    rollingIndex.models[m] = {
      model_id: m === "claude" ? "claude-sonnet-4-6" : m === "gpt4o" ? "gpt-4o-2024-11-20" : "gemini-2.5-flash",
      horizons: {
        "1d": {
          status: "active", days_until_first: 0,
          n: dates.length * 100,
          mu: Math.round(baseMu[m] * 1000) / 1000,
          accuracy: Math.round(baseAcc[m] * 10000) / 10000,
          hit_rate_90: Math.round(baseHR[m] * 1000) / 1000,
          ece_90: Math.round(Math.abs(0.90 - baseHR[m]) * 1000) / 1000,
          mean_ece: Math.round(Math.abs(0.90 - baseHR[m]) * 0.7 * 1000) / 1000,
          mean_brier: Math.round((0.001 + Math.random() * 0.003) * 10000) / 10000,
          sectors: sectorData,
          items: itemData,
        },
        "1w": { status: "insufficient_data", days_until_first: 4 },
        "1m": { status: "insufficient_data", days_until_first: 27 }
      }
    };
  });

  const timeSeries = {
    generated_at: new Date().toISOString(),
    window_days: 30,
    _mock: true,
    horizons: {
      "1d": {
        status: "active",
        dates: dates,
        models: {
          claude: { hit_rate_90: noisySeries(0.85, dates.length, 0.06), mu: noisySeries(0.92, dates.length, 0.08), accuracy: noisySeries(0.025, dates.length, 0.008), n: dates.map((_, i) => 40 * (i + 1)) },
          gpt4o:  { hit_rate_90: noisySeries(0.55, dates.length, 0.08), mu: noisySeries(0.65, dates.length, 0.10), accuracy: noisySeries(0.038, dates.length, 0.010), n: dates.map((_, i) => 40 * (i + 1)) },
          gemini: { hit_rate_90: noisySeries(0.72, dates.length, 0.07), mu: noisySeries(0.80, dates.length, 0.09), accuracy: noisySeries(0.030, dates.length, 0.009), n: dates.map((_, i) => 40 * (i + 1)) },
        },
        sectors: {}
      },
      "1w": { status: "insufficient_data" },
      "1m": { status: "insufficient_data" }
    }
  };

  // Mock per-sector time series
  sectors.forEach(sec => {
    timeSeries.horizons["1d"].sectors[sec] = {
      models: {
        claude: { hit_rate_90: noisySeries(0.85, dates.length, 0.10), mu: noisySeries(0.92, dates.length, 0.12), accuracy: noisySeries(0.025, dates.length, 0.010), n: dates.map(() => 5 + Math.round(Math.random() * 5)) },
        gpt4o:  { hit_rate_90: noisySeries(0.55, dates.length, 0.12), mu: noisySeries(0.65, dates.length, 0.14), accuracy: noisySeries(0.038, dates.length, 0.012), n: dates.map(() => 5 + Math.round(Math.random() * 5)) },
        gemini: { hit_rate_90: noisySeries(0.72, dates.length, 0.11), mu: noisySeries(0.80, dates.length, 0.13), accuracy: noisySeries(0.030, dates.length, 0.011), n: dates.map(() => 5 + Math.round(Math.random() * 5)) },
      }
    };
  });

  return { rollingIndex, timeSeries, itemsList: mockItems };
}

function generateMockItemSeries(ticker) {
  const today = new Date();
  const dates = [];
  const d = new Date(today);
  d.setDate(d.getDate() - 20);
  while (dates.length < 12) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(d.toISOString().split("T")[0]);
  }
  function ns(b,l,s){const a=[];let v=b;for(let i=0;i<l;i++){v+=(Math.random()-0.5)*s;v=Math.max(0.1,Math.min(2,v));a.push(Math.round(v*1000)/1000);}return a;}
  return {
    ticker, label: ticker, sector: "Unknown",
    horizons: {
      "1d": { status:"active", dates, models: {
        claude:{hit_rate_90:ns(0.85,dates.length,0.15),mu:ns(0.9,dates.length,0.2),accuracy:ns(0.025,dates.length,0.015),n:dates.map(()=>1)},
        gpt4o:{hit_rate_90:ns(0.55,dates.length,0.18),mu:ns(0.65,dates.length,0.22),accuracy:ns(0.038,dates.length,0.018),n:dates.map(()=>1)},
        gemini:{hit_rate_90:ns(0.72,dates.length,0.16),mu:ns(0.80,dates.length,0.21),accuracy:ns(0.030,dates.length,0.016),n:dates.map(()=>1)},
      }},
      "1w": { status: "insufficient_data" },
      "1m": { status: "insufficient_data" }
    }
  };
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
    itemsList = il;
    usingMock = false;
  } catch {
    const mock = generateMockData();
    rolling = mock.rollingIndex;
    series = mock.timeSeries;
    itemsList = mock.itemsList;
    usingMock = true;
  }

  populateSectorFilter();
  initStockSearch();
  updateStatus();
  render();
  bindTabs();
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
  await renderChart();
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
  renderTabs();
  renderChart();
  renderDomainTable();
  updateFilterLabel();
}

function renderForHorizon() {
  renderCards();
  renderChart();
  renderDomainTable();
  document.getElementById("cards-horizon-label").textContent =
    (HORIZON_LABELS[horizon] || horizon).toLowerCase() + " horizon";
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

function bindTabs() {
  document.querySelectorAll("#horizon-tabs .tab").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      horizon = btn.dataset.hz;
      document.querySelectorAll("#horizon-tabs .tab").forEach(b => {
        b.classList.toggle("active", b.dataset.hz === horizon);
        b.setAttribute("aria-selected", b.dataset.hz === horizon);
      });
      renderForHorizon();
    });
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

function renderTabs() {
  document.querySelectorAll("#horizon-tabs .tab").forEach(btn => {
    const h = btn.dataset.hz;
    const hData = series?.horizons?.[h];
    const disabled = !hData || hData.status === "insufficient_data";
    btn.disabled = disabled;
    const old = btn.querySelector(".tab-tooltip");
    if (old) old.remove();
    if (disabled) {
      const days = rolling?.models?.claude?.horizons?.[h]?.days_until_first;
      const tip = document.createElement("span");
      tip.className = "tab-tooltip";
      tip.textContent = days > 0
        ? HORIZON_LABELS[h] + " data in ~" + days + " day" + (days === 1 ? "" : "s")
        : "Insufficient data";
      btn.appendChild(tip);
    }
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

  container.innerHTML = MODEL_KEYS.map(m => {
    const cfg = MODELS[m];
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

// ── Time-series chart ────────────────────────────────────────────────────────

async function renderChart() {
  const canvas = document.getElementById("main-chart");
  const rampup = document.getElementById("chart-rampup");
  if (!canvas || !rampup) return;

  let chartData = null;

  if (filterStock) {
    const itemSeries = await fetchItemSeries(filterStock);
    chartData = itemSeries?.horizons?.[horizon];
  } else if (filterSector !== "all") {
    const secData = series?.horizons?.[horizon]?.sectors?.[filterSector];
    if (secData) chartData = { ...secData, dates: series.horizons[horizon].dates };
  } else {
    chartData = series?.horizons?.[horizon];
  }

  if (!chartData || chartData.status === "insufficient_data" || !chartData.dates?.length) {
    canvas.style.display = "none";
    rampup.style.display = "flex";
    const days = rolling?.models?.claude?.horizons?.[horizon]?.days_until_first;
    const hLabel = HORIZON_LABELS[horizon] || horizon;
    const startDate = rolling?.study_start_date;
    let dateStr = "";
    if (startDate && days > 0) {
      const resolveDate = new Date(startDate);
      resolveDate.setDate(resolveDate.getDate() + (horizon === "1w" ? 7 : 30) + 1);
      dateStr = " (" + resolveDate.toLocaleDateString(undefined, { month: "long", day: "numeric" }) + ")";
    }
    rampup.innerHTML = `
      <div class="rampup-icon">\u23F3</div>
      <div class="rampup-title">${hLabel} data building</div>
      <div class="rampup-body">
        ${days > 0
          ? hLabel + " predictions resolve in approximately <strong>" + days + " day" + (days === 1 ? "" : "s") + "</strong>" + dateStr + ". Check back then."
          : "Building " + hLabel.toLowerCase() + " data \u2014 check back soon."}
      </div>`;
    return;
  }

  canvas.style.display = "";
  rampup.style.display = "none";

  const mcfg = METRIC_CONFIG[metric];
  const labels = chartData.dates || [];
  const datasets = MODEL_KEYS.map(m => ({
    label:           MODELS[m].label,
    data:            (chartData.models?.[m]?.[metric] || []).map(v => v !== null && v !== undefined ? v : NaN),
    borderColor:     MODELS[m].color,
    backgroundColor: MODELS[m].color + "18",
    borderWidth:     2.5,
    pointRadius:     labels.length > 25 ? 0 : 3,
    pointHoverRadius: 5,
    tension:         0.3,
    spanGaps:        true,
    fill:            false,
  }));

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
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "top",
          labels: { usePointStyle: true, pointStyle: "line", padding: 16, font: { size: 12 } },
        },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.92)",
          titleFont: { size: 12 },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 6,
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.y;
              return " " + ctx.dataset.label + ": " + (isNaN(v) ? "\u2014" : mcfg.fmt(v));
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 10, font: { size: 11 }, color: "#94a3b8" },
          grid: { display: false },
        },
        y: {
          min: mcfg.min,
          max: mcfg.max,
          ticks: {
            callback: v => mcfg.fmt(v),
            font: { size: 11 },
            color: "#94a3b8",
            stepSize: metric === "mu" ? 0.2 : metric === "accuracy" ? undefined : 0.1,
          },
          grid: { color: "#f1f5f9" },
          title: {
            display: true,
            text: mcfg.label,
            font: { size: 12, weight: "600" },
            color: "#64748b",
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

  const hasData = MODEL_KEYS.some(
    m => rolling?.models?.[m]?.horizons?.[horizon]?.status === "active"
  );

  if (!hasData) {
    container.innerHTML = `
      <div style="padding:2.5rem 1rem;text-align:center;color:var(--muted);font-size:0.9rem">
        Sector breakdown unavailable &mdash; building data for ${HORIZON_LABELS[horizon] || horizon} horizon.
      </div>`;
    return;
  }

  const sectorSet = new Set();
  MODEL_KEYS.forEach(m => {
    const secs = rolling?.models?.[m]?.horizons?.[horizon]?.sectors;
    if (secs) Object.keys(secs).forEach(s => sectorSet.add(s));
  });
  const sectors = Array.from(sectorSet).sort();

  const headerCells = MODEL_KEYS.map(m =>
    `<th style="color:${MODELS[m].color}">${MODELS[m].label}</th>`
  ).join("");

  const rows = sectors.map(sec => {
    const cells = MODEL_KEYS.map(m => {
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
