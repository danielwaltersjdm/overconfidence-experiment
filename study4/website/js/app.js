/**
 * app.js — LLM Confidence Index dashboard
 *
 * Reads rolling_index.json and time_series.json from ./data/.
 * Falls back to inline mock data if files are unavailable.
 */

"use strict";

// ── Model config ─────────────────────────────────────────────────────────────

const MODELS = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gemini: { label: "Gemini", color: "#d97706" },
};
const MODEL_KEYS = Object.keys(MODELS);
const TARGET = 0.90;
const DOMAINS = ["stocks", "crypto", "forex", "weather"];
const DOMAIN_LABELS = { stocks: "Stocks", crypto: "Crypto", forex: "Forex", weather: "Weather" };
const HORIZON_LABELS = { "1d": "1-Day", "1w": "1-Week", "1m": "1-Month" };

// ── Mock data (used when real JSON is unavailable) ───────────────────────────

function generateMockData() {
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 20);
  const startStr = startDate.toISOString().split("T")[0];
  const todayStr = today.toISOString().split("T")[0];

  // Generate 20 days of dates (weekdays only)
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
      v = Math.max(0.3, Math.min(1.0, v));
      arr.push(Math.round(v * 1000) / 1000);
    }
    return arr;
  }

  const rollingIndex = {
    generated_at: new Date().toISOString(),
    window_days: 30,
    study_start_date: startStr,
    data_through: todayStr,
    _mock: true,
    models: {}
  };

  const baseRates = { claude: 0.85, gpt4o: 0.60, gemini: 0.75 };
  const domainOffsets = { stocks: -0.05, crypto: 0.05, forex: 0.02, weather: 0.03 };

  MODEL_KEYS.forEach(m => {
    const base = baseRates[m];
    const domainData = {};
    DOMAINS.forEach(dom => {
      const hr = Math.max(0.3, Math.min(1.0, base + (domainOffsets[dom] || 0) + (Math.random() - 0.5) * 0.06));
      domainData[dom] = {
        n: 10 * dates.length,
        hit_rate_90: Math.round(hr * 1000) / 1000,
        hit_rate_80: Math.round(Math.min(1, hr + 0.05) * 1000) / 1000,
        hit_rate_50: Math.round(Math.max(0, hr - 0.15) * 1000) / 1000,
      };
    });

    rollingIndex.models[m] = {
      model_id: m === "claude" ? "claude-sonnet-4-6" : m === "gpt4o" ? "gpt-4o-2024-11-20" : "gemini-2.5-flash",
      horizons: {
        "1d": {
          status: "active",
          days_until_first: 0,
          n: 40 * dates.length,
          hit_rate_90: Math.round(base * 1000) / 1000,
          hit_rate_80: Math.round((base + 0.05) * 1000) / 1000,
          hit_rate_50: Math.round((base - 0.15) * 1000) / 1000,
          ece_50: 0.05, ece_80: 0.08, ece_90: Math.round(Math.abs(0.90 - base) * 1000) / 1000,
          mean_ece: Math.round(Math.abs(0.90 - base) * 0.7 * 1000) / 1000,
          mean_brier: Math.round((0.001 + Math.random() * 0.003) * 10000) / 10000,
          domains: domainData
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
          claude: { hit_rate_90: noisySeries(0.85, dates.length, 0.06), n: dates.map((_, i) => 40 * (i + 1)) },
          gpt4o:  { hit_rate_90: noisySeries(0.60, dates.length, 0.08), n: dates.map((_, i) => 40 * (i + 1)) },
          gemini: { hit_rate_90: noisySeries(0.75, dates.length, 0.07), n: dates.map((_, i) => 40 * (i + 1)) },
        }
      },
      "1w": { status: "insufficient_data" },
      "1m": { status: "insufficient_data" }
    }
  };

  return { rollingIndex, timeSeries };
}

// ── State ────────────────────────────────────────────────────────────────────

let rolling = null;
let series = null;
let horizon = "1d";
let chart = null;
let usingMock = false;

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  setStatus("amber", "Loading data\u2026");

  try {
    const [ri, ts] = await Promise.all([
      fetchJSON("./data/rolling_index.json"),
      fetchJSON("./data/time_series.json"),
    ]);
    rolling = ri;
    series = ts;
    usingMock = false;
  } catch {
    const mock = generateMockData();
    rolling = mock.rollingIndex;
    series = mock.timeSeries;
    usingMock = true;
  }

  updateStatus();
  render();
  bindTabs();
});

// ── Data loading ─────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  if (!data || typeof data !== "object") throw new Error("Empty");
  return data;
}

// ── Status bar ───────────────────────────────────────────────────────────────

function setStatus(color, text) {
  const dot = document.getElementById("status-dot");
  const txt = document.getElementById("status-text");
  if (dot) { dot.className = "status-dot " + color; }
  if (txt) { txt.textContent = text; }
}

function updateStatus() {
  if (usingMock) {
    setStatus("amber", "Showing sample data \u2014 live data not yet available");
    return;
  }

  const gen = rolling?.generated_at;
  if (!gen) {
    setStatus("red", "Data unavailable");
    return;
  }

  const age = Date.now() - new Date(gen).getTime();
  const hours = age / (1000 * 60 * 60);

  if (hours < 26) {
    setStatus("green", "Updated " + fmtDate(gen));
  } else if (hours < 72) {
    setStatus("amber", "Updated " + fmtDate(gen));
  } else {
    setStatus("red", "Last update: " + fmtDate(gen));
  }
}

// ── Render orchestration ─────────────────────────────────────────────────────

function render() {
  renderCards();
  renderTabs();
  renderChart();
  renderDomainTable();
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

function renderTabs() {
  document.querySelectorAll("#horizon-tabs .tab").forEach(btn => {
    const h = btn.dataset.hz;
    const hData = series?.horizons?.[h];
    const disabled = !hData || hData.status === "insufficient_data";
    btn.disabled = disabled;

    // Remove old tooltip
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

function renderCards() {
  const container = document.getElementById("model-cards");
  if (!container) return;

  container.innerHTML = MODEL_KEYS.map(m => {
    const cfg = MODELS[m];
    const hData = rolling?.models?.[m]?.horizons?.[horizon];
    const active = hData?.status === "active";
    const hr90 = active ? hData.hit_rate_90 : null;
    const hr80 = active ? hData.hit_rate_80 : null;
    const hr50 = active ? hData.hit_rate_50 : null;
    const ece = active ? hData.mean_ece : null;
    const brier = active ? hData.mean_brier : null;
    const n = active ? hData.n : null;
    const badge = getBadge(hr90);

    const detailHtml = active ? `
      <div class="card-detail">
        <span>50% CI: <strong>${pct(hr50)}</strong></span>
        <span>80% CI: <strong>${pct(hr80)}</strong></span>
        <span>ECE: <strong>${ece !== null ? (ece * 100).toFixed(1) + "pp" : "\u2014"}</strong></span>
        <span>n = <strong>${n !== null ? n.toLocaleString() : "\u2014"}</strong></span>
      </div>` : "";

    return `
      <div class="card ${m}">
        <div class="card-name">${cfg.label}</div>
        <div class="card-value" style="color:${rateColor(hr90)}">${hr90 !== null ? pct(hr90) : "\u2014"}</div>
        <div class="card-label">90% CI hit rate</div>
        <span class="badge ${badge.cls}">${badge.text}</span>
        ${detailHtml}
      </div>`;
  }).join("");
}

// ── Time-series chart ────────────────────────────────────────────────────────

function renderChart() {
  const canvas = document.getElementById("main-chart");
  const rampup = document.getElementById("chart-rampup");
  if (!canvas || !rampup) return;

  const hData = series?.horizons?.[horizon];

  // Ramp-up state
  if (!hData || hData.status === "insufficient_data") {
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

  const labels = hData.dates || [];
  const datasets = MODEL_KEYS.map(m => ({
    label:           MODELS[m].label,
    data:            (hData.models?.[m]?.hit_rate_90 || []).map(v => v !== null && v !== undefined ? v : NaN),
    borderColor:     MODELS[m].color,
    backgroundColor: MODELS[m].color + "18",
    borderWidth:     2.5,
    pointRadius:     labels.length > 25 ? 0 : 3,
    pointHoverRadius: 5,
    tension:         0.3,
    spanGaps:        true,
    fill:            false,
  }));

  // Target line
  datasets.push({
    label:       "Target (90%)",
    data:        labels.map(() => TARGET),
    borderColor: "#dc2626",
    borderDash:  [6, 4],
    borderWidth: 1.5,
    pointRadius: 0,
    pointHoverRadius: 0,
    fill:        false,
  });

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
          labels: {
            usePointStyle: true,
            pointStyle: "line",
            padding: 16,
            font: { size: 12 },
          },
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
              return " " + ctx.dataset.label + ": " + (isNaN(v) ? "\u2014" : pct(v));
            }
          }
        }
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10,
            font: { size: 11 },
            color: "#94a3b8",
          },
          grid: { display: false },
        },
        y: {
          min: 0,
          max: 1,
          ticks: {
            callback: v => pct(v),
            font: { size: 11 },
            color: "#94a3b8",
            stepSize: 0.1,
          },
          grid: { color: "#f1f5f9" },
          title: {
            display: true,
            text: "90% CI Hit Rate",
            font: { size: 12, weight: "600" },
            color: "#64748b",
          },
        },
      },
    },
  });
}

// ── Domain table ─────────────────────────────────────────────────────────────

function renderDomainTable() {
  const container = document.getElementById("domain-table");
  if (!container) return;

  const hasData = MODEL_KEYS.some(
    m => rolling?.models?.[m]?.horizons?.[horizon]?.status === "active"
  );

  if (!hasData) {
    container.innerHTML = `
      <div style="padding:2.5rem 1rem;text-align:center;color:var(--muted);font-size:0.9rem">
        Domain breakdown unavailable &mdash; building data for ${HORIZON_LABELS[horizon] || horizon} horizon.
      </div>`;
    return;
  }

  const headerCells = MODEL_KEYS.map(m =>
    `<th style="color:${MODELS[m].color}">${MODELS[m].label}</th>`
  ).join("");

  const rows = DOMAINS.map(dom => {
    const cells = MODEL_KEYS.map(m => {
      const d = rolling?.models?.[m]?.horizons?.[horizon]?.domains?.[dom];
      if (!d || d.n === 0) {
        return `<td><span class="cell-val" style="color:var(--muted)">\u2014</span></td>`;
      }
      const hr = d.hit_rate_90;
      return `<td>
        <span class="cell-val" style="color:${rateColor(hr)}">${pct(hr)}</span>
        <span class="cell-n">n=${d.n}</span>
      </td>`;
    }).join("");
    return `<tr><td><strong>${DOMAIN_LABELS[dom]}</strong></td>${cells}</tr>`;
  }).join("");

  container.innerHTML = `
    <table>
      <thead><tr><th>Domain</th>${headerCells}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function pct(v) {
  if (v === null || v === undefined || isNaN(v)) return "\u2014";
  return (v * 100).toFixed(1) + "%";
}

function rateColor(hr) {
  if (hr === null || hr === undefined) return "var(--muted)";
  if (hr >= 0.85) return "var(--good)";
  if (hr >= 0.70) return "var(--warn)";
  return "var(--bad)";
}

function getBadge(hr) {
  if (hr === null || hr === undefined) return { cls: "badge-none", text: "Building data" };
  if (hr >= 0.85) return { cls: "badge-good", text: "Well calibrated" };
  if (hr >= 0.70) return { cls: "badge-warn", text: "Slightly overconfident" };
  return { cls: "badge-bad", text: "Overconfident" };
}

function fmtDate(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}
