/**
 * domains.js — Study 3 Cross-Domain Calibration
 *
 * Reads data/study3/domains.json. Chart: domains on x-axis.
 * No horizon/stock/sector filters — single cross-sectional snapshot.
 */

"use strict";

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

let data = null;
let modelKeys = [];
let domainsOrdered = [];
let metric = "mu";
let filterDomain = "all";
let chart = null;

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  setStatus("amber", "Loading data\u2026");

  try {
    const r = await fetch("./data/study3/domains.json", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    data = await r.json();
  } catch (err) {
    console.error("Failed to load data:", err);
    setStatus("red", "Failed to load data");
    return;
  }

  modelKeys = Object.keys(data.models || {});
  domainsOrdered = data.domains_ordered || [];

  setStatus("green", data.resolved_predictions + " resolved predictions across " + domainsOrdered.length + " domains");
  populateDomainSelect();
  renderCards();
  renderChart();
  renderDomainTable();
  bindMetricTabs();
  bindFilters();
});

// ── Status bar ───────────────────────────────────────────────────────────────

function setStatus(color, text) {
  const dot = document.getElementById("status-dot");
  const txt = document.getElementById("status-text");
  if (dot) dot.className = "status-dot " + color;
  if (txt) txt.textContent = text;
}

// ── Filters ─────────────────────────────────────────────────────────────────

function populateDomainSelect() {
  const sel = document.getElementById("domain-select");
  if (!sel) return;
  domainsOrdered.forEach(d => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = (data.domain_labels || {})[d] || d;
    sel.appendChild(opt);
  });
}

function bindFilters() {
  const sel = document.getElementById("domain-select");
  const clearBtn = document.getElementById("filter-clear");

  if (sel) {
    sel.addEventListener("change", () => {
      filterDomain = sel.value;
      if (clearBtn) clearBtn.style.display = filterDomain !== "all" ? "" : "none";
      updateFilterLabel();
      renderCards();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      filterDomain = "all";
      if (sel) sel.value = "all";
      clearBtn.style.display = "none";
      updateFilterLabel();
      renderCards();
    });
  }
}

function updateFilterLabel() {
  const el = document.getElementById("cards-filter-label");
  if (!el) return;
  if (filterDomain !== "all") {
    el.textContent = (data.domain_labels || {})[filterDomain] || filterDomain;
  } else {
    el.textContent = "All domains";
  }
}

function getCardData(modelKey) {
  if (filterDomain !== "all") {
    return data.models[modelKey]?.domains?.[filterDomain] || null;
  }
  return data.models[modelKey]?.aggregate || null;
}

// ── Model cards ──────────────────────────────────────────────────────────────

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

// ── Chart: domains on x-axis ─────────────────────────────────────────────────

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
        ctx.beginPath(); ctx.moveTo(x, yLo); ctx.lineTo(x, yHi); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - capW, yLo); ctx.lineTo(x + capW, yLo); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - capW, yHi); ctx.lineTo(x + capW, yHi); ctx.stroke();
        ctx.restore();
      });
    });
  }
};
Chart.register(errorBarPlugin);

function renderChart() {
  const canvas = document.getElementById("main-chart");
  if (!canvas) return;

  const mcfg = METRIC_CONFIG[metric];
  const labels = domainsOrdered.map(d => (data.domain_labels || {})[d] || d);

  const datasets = modelKeys.map(m => {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    const values = [];
    const errorBars = [];
    const nValues = [];

    domainsOrdered.forEach(d => {
      const dd = data.models[m]?.domains?.[d];
      const val = dd?.[metric] ?? null;
      values.push(val);

      const se = dd?.[mcfg.seKey] ?? null;
      if (val != null && se != null) {
        errorBars.push({ lo: val - 1.96 * se, hi: val + 1.96 * se });
      } else {
        errorBars.push(null);
      }
      nValues.push(dd?.n ?? null);
    });

    return {
      label:           cfg.label,
      data:            values.map(v => v != null ? v : NaN),
      borderColor:     cfg.color,
      backgroundColor: cfg.color + "30",
      borderWidth:     2.5,
      pointRadius:     6,
      pointHoverRadius: 8,
      tension:         0,
      spanGaps:        false,
      fill:            false,
      _errorBars:      errorBars,
      _nValues:        nValues,
    };
  });

  // Target line
  if (mcfg.target !== null) {
    datasets.push({
      label:       "Target (" + mcfg.fmt(mcfg.target) + ")",
      data:        domainsOrdered.map(() => mcfg.target),
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
            text: "Prediction Domain",
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

// ── Domain table (all 3 CI levels) ──────────────────────────────────────────

function renderDomainTable() {
  const container = document.getElementById("domain-table");
  if (!container) return;

  // Header: Domain | Claude 50/80/90 | GPT-4 50/80/90 | Gemini 50/80/90
  const modelHeaders = modelKeys.map(m => {
    const cfg = MODEL_DISPLAY[m] || { label: m, color: "#64748b" };
    return `<th colspan="3" style="color:${cfg.color};text-align:center;border-bottom:2px solid ${cfg.color}20">${cfg.label}</th>`;
  }).join("");

  const subHeaders = modelKeys.map(() =>
    '<th class="ci-sub">50%</th><th class="ci-sub">80%</th><th class="ci-sub">90%</th>'
  ).join("");

  const rows = domainsOrdered.map(d => {
    const label = (data.domain_labels || {})[d] || d;
    const cells = modelKeys.map(m => {
      const dd = data.models[m]?.domains?.[d];
      if (!dd || dd.status === "no_data") {
        return '<td colspan="3" style="text-align:center;color:var(--muted)">\u2014</td>';
      }
      return [50, 80, 90].map(level => {
        const hr = dd[`hit_rate_${level}`];
        const target = level / 100;
        const color = ciHitColor(hr, target);
        return `<td style="text-align:center"><span class="cell-val" style="color:${color}">${hr != null ? (hr * 100).toFixed(0) + "%" : "\u2014"}</span></td>`;
      }).join("");
    }).join("");

    // Find n (same across CI levels for a domain)
    const nVal = modelKeys.reduce((acc, m) => {
      const dd = data.models[m]?.domains?.[d];
      return dd?.n || acc;
    }, null);

    return `<tr><td><strong>${label}</strong> <span class="cell-n">n=${nVal || "?"}</span></td>${cells}</tr>`;
  }).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr><th rowspan="2">Domain</th>${modelHeaders}</tr>
        <tr>${subHeaders}</tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Metric tabs ─────────────────────────────────────────────────────────────

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

// ── Helpers ──────────────────────────────────────────────────────────────────

function pct(v) {
  if (v == null || isNaN(v)) return "\u2014";
  return (v * 100).toFixed(1) + "%";
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

function ciHitColor(hr, target) {
  if (hr == null || isNaN(hr)) return "var(--muted)";
  const diff = Math.abs(hr - target);
  if (diff <= 0.05) return "var(--good)";
  if (diff <= 0.15) return "var(--warn)";
  return "var(--bad)";
}
