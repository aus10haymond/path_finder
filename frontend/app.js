const BACKEND_URL = "";
const SECRET_URL_TOKEN = window.APP_TOKEN || "";

const _params = new URLSearchParams(location.search);
const TEST_MODE = _params.get("test") === "1";

if (TEST_MODE) {
  const banner = document.createElement("div");
  banner.textContent = "TEST MODE — using test sheet & test email";
  banner.style.cssText = "background:#b45309;color:#fff;text-align:center;padding:8px;font-weight:600;font-size:14px;letter-spacing:.5px;";
  document.body.prepend(banner);
}

const cities = [];
let routeMode = "per_city";
let pollInterval = null;
let activeSocket = null;

// Progress step config (ordered to match the job pipeline)
const STEPS = [
  { id: "step-fetch",   keywords: ["fetching", "starting"] },
  { id: "step-geocode", keywords: ["geocoding"] },
  { id: "step-sheets",  keywords: ["writing"] },
  { id: "step-route",   keywords: ["optimizing"] },
  { id: "step-email",   keywords: ["sending", "done"] },
];

// --- City chips ---

function addCity() {
  const input = document.getElementById("city-input");
  const name = input.value.trim();
  if (!name) return;

  if (cities.some(c => c.toLowerCase() === name.toLowerCase())) {
    input.value = "";
    return;
  }

  cities.push(name);
  input.value = "";
  renderChips();
  document.getElementById("city-error").hidden = true;
}

function removeCity(name) {
  const idx = cities.indexOf(name);
  if (idx !== -1) cities.splice(idx, 1);
  renderChips();
}

function renderChips() {
  const container = document.getElementById("city-chips");
  container.innerHTML = cities.map(city => `
    <div class="chip">
      <span>${city}</span>
      <button type="button" onclick="removeCity('${city.replace(/'/g, "\\'")}')" aria-label="Remove ${city}">×</button>
    </div>
  `).join("");
}

// Allow Enter key in city input
document.getElementById("city-input").addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); addCity(); }
});

// --- Route mode ---

function setMode(mode) {
  routeMode = mode;
  document.getElementById("mode-per-city").classList.toggle("active", mode === "per_city");
  document.getElementById("mode-all-cities").classList.toggle("active", mode === "all_cities");
}

// --- Same address toggle ---

function toggleSameAddress() {
  const checked = document.getElementById("same-address").checked;
  const endInput = document.getElementById("end-address");
  endInput.disabled = checked;
  if (checked) {
    endInput.value = document.getElementById("start-address").value;
  }
}

document.getElementById("start-address").addEventListener("input", () => {
  if (document.getElementById("same-address").checked) {
    document.getElementById("end-address").value =
      document.getElementById("start-address").value;
  }
});

// --- Form submit ---

async function submitForm() {
  const startAddress = document.getElementById("start-address").value.trim();
  let endAddress = document.getElementById("end-address").value.trim();
  const sameAddress = document.getElementById("same-address").checked;

  let valid = true;

  if (cities.length === 0) {
    document.getElementById("city-error").hidden = false;
    valid = false;
  }
  if (!startAddress) {
    document.getElementById("start-error").hidden = false;
    valid = false;
  } else {
    document.getElementById("start-error").hidden = true;
  }
  if (!valid) return;

  if (sameAddress || !endAddress) endAddress = startAddress;

  setLoading(true);
  showSection("progress");
  resetSteps();

  try {
    const endpoint = TEST_MODE ? "/api/test" : "/api/generate";
    const resp = await fetch(`${BACKEND_URL}${endpoint}?token=${SECRET_URL_TOKEN}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cities,
        start_address: startAddress,
        end_address: endAddress,
        route_mode: routeMode,
      }),
    });

    if (resp.status === 429) {
      showError("A job is already running. Please wait a few minutes before generating again.");
      return;
    }
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      showError(data.detail || "Failed to start job. Please try again.");
      return;
    }

    const { job_id } = await resp.json();
    connectWebSocket(job_id);
  } catch (err) {
    showError("Could not reach the server. Make sure the backend is running.");
  }
}

// --- WebSocket (primary) ---

function connectWebSocket(jobId) {
  if (activeSocket) {
    activeSocket.close();
    activeSocket = null;
  }

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/api/ws/${jobId}`);
  activeSocket = ws;

  ws.onmessage = event => {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }

    if (data.ping) return; // keepalive, ignore

    if (data.progress) {
      document.getElementById("progress-text").textContent = data.progress;
      updateStep(data.progress);
    }

    if (data.status === "complete") {
      ws.close();
      activeSocket = null;
      showResults(data.result);
      if (navigator.vibrate) navigator.vibrate(200);
    } else if (data.status === "failed") {
      ws.close();
      activeSocket = null;
      showError(data.error || "Job failed. Please try again.");
    }
  };

  ws.onerror = () => {
    activeSocket = null;
    startPolling(jobId); // fall back to polling
  };

  ws.onclose = event => {
    if (activeSocket === ws) activeSocket = null;
    // Unexpected close before terminal state → fall back to polling
    if (!event.wasClean) startPolling(jobId);
  };
}

// --- Progress steps ---

function resetSteps() {
  STEPS.forEach(s => {
    const el = document.getElementById(s.id);
    el.classList.remove("active", "done");
  });
}

function updateStep(progressText) {
  const text = progressText.toLowerCase();
  let activeIdx = -1;
  for (let i = 0; i < STEPS.length; i++) {
    if (STEPS[i].keywords.some(kw => text.includes(kw))) {
      activeIdx = i;
      break;
    }
  }
  if (activeIdx < 0) return;

  STEPS.forEach((s, i) => {
    const el = document.getElementById(s.id);
    if (i < activeIdx) {
      el.classList.add("done");
      el.classList.remove("active");
    } else if (i === activeIdx) {
      el.classList.add("active");
      el.classList.remove("done");
    } else {
      el.classList.remove("active", "done");
    }
  });
}

// --- Polling fallback ---

function startPolling(jobId) {
  if (pollInterval) return; // already polling
  pollInterval = setInterval(() => pollStatus(jobId), 4000);
}

async function pollStatus(jobId) {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/status/${jobId}`);
    if (!resp.ok) return;
    const data = await resp.json();

    if (data.progress) {
      document.getElementById("progress-text").textContent = data.progress;
      updateStep(data.progress);
    }

    if (data.status === "complete") {
      clearInterval(pollInterval);
      pollInterval = null;
      showResults(data.result);
      if (navigator.vibrate) navigator.vibrate(200);
    } else if (data.status === "failed") {
      clearInterval(pollInterval);
      pollInterval = null;
      showError(data.error || "Job failed. Please try again.");
    }
  } catch {
    // network blip — keep polling
  }
}

// --- Results ---

function showResults(result) {
  setLoading(false);
  showSection("results");

  // Mark all steps done
  STEPS.forEach(s => {
    const el = document.getElementById(s.id);
    el.classList.add("done");
    el.classList.remove("active");
  });

  const summary = `${result.city_count} ${result.city_count === 1 ? "city" : "cities"} · ${result.agent_count} agents found`;
  document.getElementById("result-summary").textContent = summary;

  // Failed cities warning
  const failedEl = document.getElementById("failed-cities-warning");
  if (result.failed_cities && result.failed_cities.length > 0) {
    failedEl.textContent = `Could not retrieve agents for: ${result.failed_cities.join(", ")}`;
    failedEl.hidden = false;
  } else {
    failedEl.hidden = true;
  }

  const link = document.getElementById("sheet-link");
  link.href = result.sheet_url;

  const routeContainer = document.getElementById("route-summary");
  routeContainer.innerHTML = "";

  const routes = result.routes || {};
  const keys = Object.keys(routes);

  if (keys.length === 0) {
    if (result.route_warning) {
      routeContainer.innerHTML = `<p class="route-warning">${result.route_warning}</p>`;
    }
    return;
  }

  keys.forEach(key => {
    const route = routes[key];
    const label = key === "all" ? "All Cities Combined" : key;
    const mins = route.duration_minutes;
    const duration = mins >= 60
      ? `${Math.floor(mins / 60)}h ${mins % 60}m`
      : `${mins}m`;

    routeContainer.innerHTML += `
      <div class="route-block">
        <h3>${label}</h3>
        <p class="route-meta">${route.stop_count} stops · Est. ${duration} driving</p>
        ${mapsLinks(route.ordered_agents || [])}
        ${renderStopList(route.ordered_agents || [])}
      </div>`;
  });

  if (result.route_warning) {
    routeContainer.innerHTML += `<p class="route-warning">${result.route_warning}</p>`;
  }

  routeContainer.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Google Maps deep-link generation — segments of up to 9 stops with 1-stop overlap
const MAPS_SEGMENT = 9;

function mapsLinks(stops) {
  if (stops.length < 2) return "";

  function segUrl(chunk) {
    const parts = chunk.map(s => encodeURIComponent(`${s.address}, ${s.city}`));
    return `https://www.google.com/maps/dir/${parts.join("/")}`;
  }

  if (stops.length <= MAPS_SEGMENT) {
    return `<div class="maps-links"><a href="${segUrl(stops)}" target="_blank" rel="noopener" class="btn-maps">Open in Google Maps</a></div>`;
  }

  // Overlapping segments so route is continuous across chunks
  let html = '<div class="maps-links">';
  for (let i = 0; i < stops.length - 1; i += MAPS_SEGMENT - 1) {
    const chunk = stops.slice(i, i + MAPS_SEGMENT);
    const to = Math.min(i + MAPS_SEGMENT, stops.length);
    html += `<a href="${segUrl(chunk)}" target="_blank" rel="noopener" class="btn-maps">Maps: stops ${i + 1}–${to}</a>`;
  }
  return html + "</div>";
}

function renderStopList(stops) {
  const PREVIEW = 8;
  let html = '<ul class="stop-list">';
  stops.forEach((a, i) => {
    const hidden = i >= PREVIEW ? ' class="stop-hidden"' : "";
    html += `<li${hidden}>
      <span class="stop-num">${i + 1}.</span>
      <span>${a.name} — ${a.address}</span>
    </li>`;
  });
  html += "</ul>";
  if (stops.length > PREVIEW) {
    html += `<button class="btn-link" onclick="expandStops(this)">Show all ${stops.length} stops</button>`;
  }
  return html;
}

function expandStops(btn) {
  btn.previousElementSibling.querySelectorAll(".stop-hidden").forEach(el => el.classList.remove("stop-hidden"));
  btn.remove();
}

// --- Error ---

function showError(msg) {
  setLoading(false);
  showSection("error");
  document.getElementById("error-text").textContent = msg;
}

function resetForm() {
  if (activeSocket) { activeSocket.close(); activeSocket = null; }
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  showSection("none");
  setLoading(false);
  resetSteps();
}

// --- Helpers ---

function setLoading(loading) {
  document.getElementById("generate-btn").disabled = loading;
  document.getElementById("generate-btn").textContent = loading ? "Running…" : "Generate";
}

function showSection(name) {
  document.getElementById("progress-section").style.display = name === "progress" ? "flex" : "none";
  document.getElementById("results-section").style.display = name === "results" ? "block" : "none";
  document.getElementById("error-section").style.display = name === "error" ? "block" : "none";

  if (name === "progress") {
    document.getElementById("progress-section").scrollIntoView({ behavior: "smooth" });
  }
}
