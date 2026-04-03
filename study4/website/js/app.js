/**
 * app.js — Study 4 LLM CI Index website
 *
 * Reads rolling_index.json and time_series.json from ./data/.
 * All data processing happens client-side; no backend required.
 */

"use strict";

// ── Constants ──────────────────────────────────────────────────────────────────

const MODEL_CONFIG = {
  claude: { label: "Claude",  color: "#7c3aed" },
  gpt4o:  { label: "GPT-4o", color: "#059669" },
  gemini: { label: "Gemini",  color: "#d97706" },
};
const MODEL_NAMES = Object.keys(MODEL_CONFIG);
const TARGET_HIT_RATE = 0.90;

// ── State ──────────────────────────────────────────────────────────────────────

let rollingIndex  = null;
let timeSeries    = null;
let activeHorizon = "1d";
let tsChart       = null;
let domainChart   = null;

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  setStatus("loading", "Loading data…");

  try {
    const [ri, ts] = await Promise.all([
      fetchJSON("./data/rolling_index.json"),
      fetchJSON("./data/time_series.json"),
    ]);
    rollingIndex = ri;
    timeSeries   = ts;
    setStatus("ok", `Updated ${formatDate(ri.generated_at)}`);
    render();
  } catch (err) {
    setStatus("error", "Data unavailable — check back soon.");
    showGlobalError();
    console.error(err);
  }

  // Horizon tab listeners
  document.querySelectorAll(".horizon-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      activeHorizon = btn.dataset.horizon;
      document.querySelectorAll(".horizon-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderForHorizon();
    });
  });
});

// ── Data loading ───────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} loading ${url}`);
  return resp.json();
}

// ── Top-level render ───────────────────────────────────────────────────────────

function render() {
  renderHorizonTabs();
  renderModelCards();
  renderForHorizon();
}

function renderForHorizon() {
  renderTimeSeries();
  renderDomainTable();
}

// ── Horizon tabs ───────────────────────────────────────────────────────────────

function renderHorizonTabs() {
  const horizons = ["1d", "1w", "1m"];
  document.querySelectorAll(".horizon-tab").forEach((btn) => {
    const h = btn.dataset.horizon;
    const hData = timeSeries?.horizons?.[h];
    const active = h === "1d";
    btn.classList.toggle("active", active);
    // Disable horizons with no data yet
    btn.disabled = hData?.status === "insufficient_data" && h !== "1d";
    if (btn.disabled) {
      const days = rollingIndex?.models?.claude?.horizons?.[h]?.days_until_first;
      btn.title = days
        ? `First ${horizonLabel(h)} outcomes resolve in ~${days} days`
        : "Insufficient data";
    }
  });
}

// ── Model cards ────────────────────────────────────────────────────────────────

function renderModelCards() {
  const container = document.getElementById("model-cards");
  if (!container) return;

  container.innerHTML = MODEL_NAMES.map((m) => {
    const cfg = MODEL_CONFIG[m];
    const hData = rollingIndex?.models?.[m]?.horizons?.["1d"];
    const active = hData?.status === "active";
    const hr = active ? hData.hit_rate_90 : null;
    const { cls, label: badgeLabel } = hitRateBadge(hr);

    return `
      <div class="model-card ${m}">
        <div class="model-name">${cfg.label}</div>
        <div class="hit-rate" style="color:${rateColor(hr)}">${hr !== null ? pct(hr) : "—"}</div>
        <div class="hit-rate-label">30-day 90% CI hit rate (1-day horizon)</div>
        <span class="status-badge ${cls}">${badgeLabel}</span>
      </div>`;
  }).join("");
}

// ── Time-series chart ──────────────────────────────────────────────────────────

function renderTimeSeries() {
  const el = document.getElementById("ts-chart");
  if (!el) return;

  const hData = timeSeries?.horizons?.[activeHorizon];

  // Ramp-up state
  if (!hData || hData.status === "insufficient_data") {
    showRampup("ts-chart-wrap", horizonLabel(activeHorizon));
    return;
  }

  hideRampup("ts-chart-wrap");
  const ctx = el.getContext("2d");
  const labels = hData.dates || [];

  const datasets = MODEL_NAMES.map((m) => ({
    label:            MODEL_CONFIG[m].label,
    data:             (hData.models?.[m]?.hit_rate_90 || []).map((v) => v !== null ? v : NaN),
    borderColor:      MODEL_CONFIG[m].color,
    backgroundColor:  MODEL_CONFIG[m].color + "22",
    borderWidth:      2.5,
    pointRadius:      labels.length > 30 ? 0 : 3,
    tension:          0.3,
    spanGaps:         true,
  }));

  // Target line
  datasets.push({
    label:       "Target (90%)",
    data:        labels.map(() => TARGET_HIT_RATE),
    borderColor: "#dc2626",
    borderDash:  [6, 4],
    borderWidth: 1.5,
    pointRadius: 0,
    fill:        false,
  });

  if (tsChart) tsChart.destroy();
  tsChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y;
              return ` ${ctx.dataset.label}: ${isNaN(v) ? "—" : pct(v)}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 12,
            font: { size: 11 },
          },
          grid: { display: false },
        },
        y: {
          min: 0, max: 1,
          ticks: {
            callback: (v) => pct(v),
            font: { size: 11 },
          },
          title: { display: true, text: "90% CI Hit Rate" },
        },
      },
    },
  });
}

// ── Domain table ───────────────────────────────────────────────────────────────

function renderDomainTable() {
  const container = document.getElementById("domain-table-wrap");
  if (!container) return;

  // Check if any model has active data for this horizon
  const hasData = MODEL_NAMES.some(
    (m) => rollingIndex?.models?.[m]?.horizons?.[activeHorizon]?.status === "active"
  );

  if (!hasData) {
    container.innerHTML = `<div class="rampup-msg"><p>Domain breakdown unavailable — data building for ${horizonLabel(activeHorizon)} horizon.</p></div>`;
    return;
  }

  const domains = ["stocks", "crypto", "forex", "weather"];
  const domainLabels = {
    stocks:  "Stocks",
    crypto:  "Crypto",
    forex:   "Forex",
    weather: "Weather",
  };

  const modelHeaders = MODEL_NAMES.map(
    (m) => `<th style="color:${MODEL_CONFIG[m].color}">${MODEL_CONFIG[m].label}</th>`
  ).join("");

  const rows = domains.map((dom) => {
    const cells = MODEL_NAMES.map((m) => {
      const d = rollingIndex?.models?.[m]?.horizons?.[activeHorizon]?.domains?.[dom];
      if (!d || d.n === 0) return `<td><span class="cell-value" style="color:var(--color-muted)">—</span></td>`;
      const hr = d.hit_rate_90;
      return `<td><span class="cell-value" style="color:${rateColor(hr)}">${pct(hr)}</span> <small style="color:var(--color-muted)">n=${d.n}</small></td>`;
    }).join("");
    return `<tr><td><strong>${domainLabels[dom]}</strong></td>${cells}</tr>`;
  }).join("");

  container.innerHTML = `
    <table>
      <thead><tr><th>Domain</th>${modelHeaders}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Ramp-up helpers ────────────────────────────────────────────────────────────

function showRampup(wrapId, horizonName) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  const canvas = wrap.querySelector("canvas");
  if (canvas) canvas.style.display = "none";

  let msg = wrap.querySelector(".rampup-msg");
  if (!msg) {
    msg = document.createElement("div");
    msg.className = "rampup-msg";
    wrap.appendChild(msg);
  }

  // Days until first data
  const modelHData = rollingIndex?.models?.claude?.horizons?.[activeHorizon];
  const days = modelHData?.days_until_first;
  const text = days > 0
    ? `First ${horizonName} outcomes resolve in approximately <strong>${days} day${days === 1 ? "" : "s"}</strong>. Check back then.`
    : `Building ${horizonName} data — check back soon.`;

  msg.innerHTML = `<div class="rampup-icon">📈</div><p>${text}</p>`;
  msg.style.display = "block";
}

function hideRampup(wrapId) {
  const wrap = document.getElementById(wrapId);
  if (!wrap) return;
  const canvas = wrap.querySelector("canvas");
  if (canvas) canvas.style.display = "";
  const msg = wrap.querySelector(".rampup-msg");
  if (msg) msg.style.display = "none";
}

// ── Status bar ─────────────────────────────────────────────────────────────────

function setStatus(state, text) {
  const bar = document.getElementById("data-status");
  if (!bar) return;
  bar.className = `data-status ${state}`;
  bar.querySelector(".status-text").textContent = text;
}

function showGlobalError() {
  const container = document.getElementById("model-cards");
  if (container) {
    container.innerHTML = `
      <div style="grid-column:1/-1;padding:2rem;text-align:center;color:var(--color-muted)">
        <p>Data could not be loaded. The study may not have started yet, or an error occurred.</p>
        <p style="margin-top:0.5rem;font-size:0.85rem">
          Check back after <strong>Day 1</strong> of data collection, or
          <a href="https://github.com">view the raw data on GitHub</a>.
        </p>
      </div>`;
  }
}

// ── Utility ────────────────────────────────────────────────────────────────────

function pct(v) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return (v * 100).toFixed(1) + "%";
}

function rateColor(hr) {
  if (hr === null || hr === undefined) return "var(--color-muted)";
  if (hr >= 0.85) return "var(--color-good)";
  if (hr >= 0.70) return "var(--color-warn)";
  return "var(--color-bad)";
}

function hitRateBadge(hr) {
  if (hr === null || hr === undefined) return { cls: "badge-none", label: "Building data" };
  if (hr >= 0.85) return { cls: "badge-good", label: "Well calibrated" };
  if (hr >= 0.70) return { cls: "badge-warn", label: "Slightly overconfident" };
  return { cls: "badge-bad", label: "Overconfident" };
}

function horizonLabel(h) {
  return { "1d": "1-Day", "1w": "1-Week", "1m": "1-Month" }[h] || h;
}

function formatDate(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}
