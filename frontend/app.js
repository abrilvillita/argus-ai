const API = "";
const state = {
  devices: {},        // device_id -> { metric -> {value, created_at} }
  series: {},         // "device_id|metric" -> [{x,y}]
  activeSeriesKey: null,
  chart: null,
};

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

async function jsonFetch(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = `toast show${isError ? " error" : ""}`;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.className = "toast", 2800);
}

function seriesKey(deviceId, metric) { return `${deviceId}|${metric}`; }

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  const statusEl = document.getElementById("ws-status");

  ws.onopen = () => { statusEl.textContent = "live"; statusEl.classList.add("live"); };
  ws.onclose = () => { statusEl.textContent = "reconnecting…"; statusEl.classList.remove("live"); setTimeout(connectWS, 2500); };
  ws.onerror = () => ws.close();
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
  const count = Object.keys(state.devices).length;
  document.getElementById("fleet-health").textContent = count ? `${count} connected` : "Waiting for data";
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
          x: { type: "linear", ticks: { color: "#8b98a5", maxTicksLimit: 7, callback: value => new Date(value).toLocaleTimeString([], { minute: "2-digit", second: "2-digit" }) }, grid: { color: "#1f2937" } },
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
  try {
    const [devices, alerts, rules] = await Promise.all([
      jsonFetch(`${API}/api/devices`), jsonFetch(`${API}/api/alerts`), jsonFetch(`${API}/api/rules`),
    ]);
    devices.forEach(d => {
      state.devices[d.device_id] ??= {};
      state.devices[d.device_id][d.metric] = { value: d.value, created_at: d.created_at };
    });
    renderDevices(); alerts.reverse().forEach(handleAlert); renderRules(rules);
    document.getElementById("app-message").classList.add("hidden");
    await updateStats(); connectWS();
  } catch (_) {
    document.getElementById("app-message").textContent = "The free demo is still waking up. Retrying automatically…";
    setTimeout(loadInitial, 4000);
  }
}

async function updateStats() {
  try {
    const stats = await jsonFetch(`${API}/api/stats`);
    document.getElementById("stat-devices").textContent = stats.devices;
    document.getElementById("stat-readings").textContent = compact.format(stats.readings);
    document.getElementById("stat-alerts").textContent = compact.format(stats.alerts);
    document.getElementById("stat-rules").textContent = stats.active_rules;
  } catch (_) { /* Live telemetry remains usable if stats are unavailable. */ }
}

function renderRules(rules) {
  const list = document.getElementById("rule-list");
  list.innerHTML = "";
  rules.forEach((r) => {
    const li = document.createElement("li");
    li.innerHTML = `<button data-id="${r.id}">✕</button>${r.name}: ${r.device_id} ${r.metric} ${r.operator} ${r.threshold} → ${r.action}`;
    li.querySelector("button").onclick = async () => {
      if (!confirm(`Delete rule “${r.name}”?`)) return;
      await jsonFetch(`${API}/api/rules/${r.id}`, { method: "DELETE" });
      const rules = await jsonFetch(`${API}/api/rules`);
      renderRules(rules);
      updateStats(); showToast("Automation deleted");
    };
    list.appendChild(li);
  });
}

document.getElementById("rule-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  payload.threshold = parseFloat(payload.threshold);
  const button = e.target.querySelector("button"); button.disabled = true; button.textContent = "Creating…";
  try {
    await jsonFetch(`${API}/api/rules`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    renderRules(await jsonFetch(`${API}/api/rules`)); e.target.reset(); updateStats(); showToast("Automation is live");
  } catch (_) { showToast("Could not create the automation", true); }
  finally { button.disabled = false; button.textContent = "Create automation"; }
});

loadInitial();
