const API = "";
const state = {
  devices: {},        // device_id -> { metric -> {value, created_at} }
  series: {},         // "device_id|metric" -> [{x,y}]
  activeSeriesKey: null,
  chart: null,
};

function seriesKey(deviceId, metric) { return `${deviceId}|${metric}`; }

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  const statusEl = document.getElementById("ws-status");

  ws.onopen = () => { statusEl.textContent = "live"; statusEl.classList.add("live"); };
  ws.onclose = () => { statusEl.textContent = "disconnected"; statusEl.classList.remove("live"); setTimeout(connectWS, 2000); };
  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "telemetry") handleTelemetry(msg);
    if (msg.type === "alert") handleAlert(msg);
  };
}

function handleTelemetry(msg) {
  state.devices[msg.device_id] ??= {};
  state.devices[msg.device_id][msg.metric] = { value: msg.value, created_at: msg.created_at };
  renderDevices();

  const key = seriesKey(msg.device_id, msg.metric);
  state.series[key] ??= [];
  state.series[key].push({ x: msg.created_at * 1000, y: msg.value });
  if (state.series[key].length > 100) state.series[key].shift();

  renderTabs();
  if (state.activeSeriesKey === null) state.activeSeriesKey = key;
  if (state.activeSeriesKey === key) renderChart();
}

function handleAlert(msg) {
  const list = document.getElementById("alert-list");
  const li = document.createElement("li");
  li.className = msg.source && msg.source.startsWith("rule:") ? "" : "anomaly";
  const when = new Date(msg.created_at * 1000).toLocaleTimeString();
  li.innerHTML = `<strong>${msg.device_id}</strong> — ${msg.message}` +
    (msg.action_taken ? ` <em>(action: ${msg.action_taken})</em>` : "") +
    `<span class="time">${when} · source: ${msg.source}</span>`;
  list.prepend(li);
  while (list.children.length > 50) list.removeChild(list.lastChild);
}

function renderDevices() {
  const container = document.getElementById("device-list");
  container.innerHTML = "";
  const ruleDeviceSelect = document.getElementById("rule-device");
  const existing = new Set(Array.from(ruleDeviceSelect.options).map(o => o.value));

  Object.entries(state.devices).forEach(([deviceId, metrics]) => {
    if (!existing.has(deviceId)) {
      const opt = document.createElement("option");
      opt.value = deviceId; opt.textContent = deviceId;
      ruleDeviceSelect.appendChild(opt);
    }
    const card = document.createElement("div");
    card.className = "device-card";
    const rows = Object.entries(metrics).map(([m, d]) =>
      `<div class="metric-row"><span>${m}</span><span>${d.value.toFixed(2)}</span></div>`
    ).join("");
    card.innerHTML = `<div class="name">${deviceId}</div>${rows}`;
    container.appendChild(card);
  });
}

function renderTabs() {
  const tabs = document.getElementById("chart-tabs");
  tabs.innerHTML = "";
  Object.keys(state.series).forEach((key) => {
    const btn = document.createElement("button");
    btn.textContent = key.replace("|", " · ");
    btn.className = key === state.activeSeriesKey ? "active" : "";
    btn.onclick = () => { state.activeSeriesKey = key; renderTabs(); renderChart(); };
    tabs.appendChild(btn);
  });
}

function renderChart() {
  const ctx = document.getElementById("metric-chart");
  const data = state.series[state.activeSeriesKey] || [];
  if (!state.chart) {
    state.chart = new Chart(ctx, {
      type: "line",
      data: { datasets: [{ label: state.activeSeriesKey, data, borderColor: "#4fd1c5", tension: .3, pointRadius: 0 }] },
      options: {
        animation: false,
        scales: {
          x: { type: "time", time: { unit: "second" }, ticks: { color: "#8b98a5" }, grid: { color: "#1f2937" } },
          y: { ticks: { color: "#8b98a5" }, grid: { color: "#1f2937" } },
        },
        plugins: { legend: { labels: { color: "#e6edf3" } } },
      },
    });
  } else {
    state.chart.data.datasets[0].label = state.activeSeriesKey;
    state.chart.data.datasets[0].data = data;
    state.chart.update("none");
  }
}

async function loadInitial() {
  const [devices, alerts, rules] = await Promise.all([
    fetch(`${API}/api/devices`).then(r => r.json()),
    fetch(`${API}/api/alerts`).then(r => r.json()),
    fetch(`${API}/api/rules`).then(r => r.json()),
  ]);
  devices.forEach(d => {
    state.devices[d.device_id] ??= {};
    state.devices[d.device_id][d.metric] = { value: d.value, created_at: d.created_at };
  });
  renderDevices();
  alerts.reverse().forEach(handleAlert);
  renderRules(rules);
}

function renderRules(rules) {
  const list = document.getElementById("rule-list");
  list.innerHTML = "";
  rules.forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `<button data-id="${r.id}">✕</button>${r.name}: ${r.device_id} ${r.metric} ${r.operator} ${r.threshold} → ${r.action}`;
    li.querySelector("button").onclick = async () => {
      await fetch(`${API}/api/rules/${r.id}`, { method: "DELETE" });
      const rules = await fetch(`${API}/api/rules`).then(res => res.json());
      renderRules(rules);
    };
    list.appendChild(li);
  });
}

document.getElementById("rule-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  payload.threshold = parseFloat(payload.threshold);
  await fetch(`${API}/api/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const rules = await fetch(`${API}/api/rules`).then(res => res.json());
  renderRules(rules);
  e.target.reset();
});

// Chart.js time scale needs the date adapter; load it before first render.
const adapterScript = document.createElement("script");
adapterScript.src = "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js";
adapterScript.onload = () => { loadInitial(); connectWS(); };
document.head.appendChild(adapterScript);
