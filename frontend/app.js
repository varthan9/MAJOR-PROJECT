const api = (path) => fetch(path).then((response) => response.json());
let stores = [];
let sensorHistory = [];

function setText(id, value) { document.getElementById(id).textContent = value; }

function renderChart(metric = 'temperature') {
  const svg = document.getElementById('chart');
  const values = sensorHistory.map((item) => item[metric]);
  const min = Math.min(...values); const max = Math.max(...values); const range = max - min || 1;
  const points = values.map((value, index) => `${35 + index * 126},${185 - ((value - min) / range) * 145}`).join(' ');
  const area = `35,185 ${points} 665,185`;
  svg.innerHTML = `<line class="grid-line" x1="35" y1="40" x2="665" y2="40"/><line class="grid-line" x1="35" y1="112" x2="665" y2="112"/><line class="grid-line" x1="35" y1="185" x2="665" y2="185"/><polygon class="chart-area" points="${area}"/><polyline class="chart-line" points="${points}"/>${values.map((value, index) => `<circle class="chart-dot" cx="${35 + index * 126}" cy="${185 - ((value - min) / range) * 145}" r="4"/>`).join('')}${sensorHistory.map((item, index) => `<text class="chart-label" x="${25 + index * 126}" y="210">${item.time}</text>`).join('')}`;
}

function renderHistory(items) {
  document.getElementById('predictionHistory').innerHTML = items.map((item) => `<div class="history-item"><span class="history-condition ${item.condition.toLowerCase()}">${item.condition}</span><span class="history-time">${item.time}</span><span class="history-confidence">${Math.round(item.confidence * 100)}%</span></div>`).join('');
}

function renderStores(decision) {
  document.getElementById('storeList').innerHTML = stores.map((store) => {
    const score = decision.store_scores.find((item) => item.store_id === store.id)?.score || 0;
    return `<div class="store-option ${store.id === decision.store_id ? 'selected' : ''}" data-store-id="${store.id}"><header><span>${store.name}</span><span class="score">${Math.round(score * 100)}% fit</span></header><p>${store.distance_km} km away · ${store.demand}/${store.capacity} crate demand</p></div>`;
  }).join('');
  document.querySelectorAll('.store-option').forEach((element) => element.addEventListener('click', () => selectStore(element.dataset.storeId)));
}

function renderVehicles(items, selectedId) {
  document.getElementById('vehicleList').innerHTML = items.map((vehicle) => `<div class="vehicle ${vehicle.id === selectedId ? 'selected' : ''}"><strong>${vehicle.name}${vehicle.id === selectedId ? ' ✓' : ''}</strong><small class="${vehicle.available ? 'available' : 'busy'}">${vehicle.available ? `Available · ${vehicle.distance_km} km away` : 'Currently busy'}</small></div>`).join('');
}

function renderAgents(items) {
  document.getElementById('agentList').innerHTML = items.map((agent) => `<div class="agent-row"><span class="agent-dot"></span><div><strong>${agent.name}</strong><small>${agent.role}</small></div><span class="agent-status">${agent.status}</span></div>`).join('');
}

function applyOverview(data, history, vehicleData) {
  const { prediction, decision } = data;
  setText('confidence', `${Math.round(prediction.confidence * 100)}%`); setText('shelfLife', `${prediction.remaining_shelf_life_days} days`);
  setText('temperature', `${prediction.temperature} °C`); setText('humidity', `${prediction.humidity} %`); setText('pressure', `${prediction.pressure} hPa`); setText('gasResistance', `${(prediction.gas_resistance / 1000).toFixed(1)} kΩ`);
  setText('destination', `${decision.destination} · ${stores.find((store) => store.id === decision.store_id)?.name.split(' · ')[1] || ''}`); setText('mapStore', decision.destination); setText('distance', `${decision.distance_km} km`); setText('eta', `${decision.route_minutes} min`); setText('taskDestination', decision.destination);
  renderChart(); renderHistory(history); renderStores(decision); renderVehicles(vehicleData, decision.vehicle_id); renderAgents(data.agents);
}

async function loadDashboard(storeId) {
  const suffix = storeId ? `?store_id=${storeId}` : '';
  const [overview, history, vehicleData] = await Promise.all([api(`/api/overview${suffix}`), api('/api/predictions/history'), api('/api/vehicles')]);
  applyOverview(overview, history, vehicleData);
}

async function selectStore(storeId) { await loadDashboard(storeId); }

Promise.all([api('/api/stores'), api('/api/sensors/history')]).then(([storeData, history]) => { stores = storeData; sensorHistory = history; return loadDashboard(); });
document.getElementById('chartSelect').addEventListener('change', (event) => renderChart(event.target.value));
document.getElementById('refreshButton').addEventListener('click', () => loadDashboard());