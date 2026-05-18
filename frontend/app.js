const BACKEND_URL = "";
const SECRET_URL_TOKEN = "3172be0f8549adc6";

const cities = [];
let routeMode = "per_city";
let pollInterval = null;

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

  try {
    const resp = await fetch(`${BACKEND_URL}/api/generate?token=${SECRET_URL_TOKEN}`, {
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
    startPolling(job_id);
  } catch (err) {
    showError("Could not reach the server. Make sure the backend is running.");
  }
}

// --- Polling ---

function startPolling(jobId) {
  pollInterval = setInterval(() => pollStatus(jobId), 4000);
}

async function pollStatus(jobId) {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/status/${jobId}`);
    if (!resp.ok) return;
    const data = await resp.json();

    if (data.progress) {
      document.getElementById("progress-text").textContent = data.progress;
    }

    if (data.status === "complete") {
      clearInterval(pollInterval);
      showResults(data.result);
      if (navigator.vibrate) navigator.vibrate(200);
    } else if (data.status === "failed") {
      clearInterval(pollInterval);
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

  const summary = `${result.city_count} ${result.city_count === 1 ? "city" : "cities"} · ${result.agent_count} agents found`;
  document.getElementById("result-summary").textContent = summary;

  const link = document.getElementById("sheet-link");
  link.href = result.sheet_url;

  const routeContainer = document.getElementById("route-summary");
  routeContainer.innerHTML = "";

  const routes = result.routes || {};
  const keys = Object.keys(routes);

  if (keys.length === 0) return;

  keys.forEach(key => {
    const route = routes[key];
    const label = key === "all" ? "All Cities Combined" : key;
    const mins = route.duration_minutes;
    const duration = mins >= 60
      ? `${Math.floor(mins / 60)}h ${mins % 60}m`
      : `${mins}m`;

    const stops = (route.ordered_agents || []).map((a, i) => `
      <li>
        <span class="stop-num">${i + 1}.</span>
        <span>${a.name} — ${a.address}</span>
      </li>`).join("");

    routeContainer.innerHTML += `
      <div class="route-block">
        <h3>${label}</h3>
        <p class="route-meta">${route.stop_count} stops · Est. ${duration} driving</p>
        <ul class="stop-list">${stops}</ul>
      </div>`;
  });

  routeContainer.scrollIntoView({ behavior: "smooth", block: "start" });
}

// --- Error ---

function showError(msg) {
  setLoading(false);
  showSection("error");
  document.getElementById("error-text").textContent = msg;
}

function resetForm() {
  showSection("none");
  setLoading(false);
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
