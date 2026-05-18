# PLAN.md — Insurance Agent Lead Finder: Full Implementation Plan

## Free-Tier Stack

| Component | Service | Limit |
|---|---|---|
| Data acquisition | SerpApi | 100 searches/month free |
| Route optimization | OpenRouteService | 2,000 req/day, 50 stops/request |
| Email | SendGrid | 100 emails/day free |
| Google Sheets | Google Cloud Service Account | Free |
| Backend | FastAPI + asyncio | — |
| Database | SQLite (file) | — |
| Backend hosting | Railway or Render | 500 hrs/month free |
| Frontend hosting | Vercel | Free |

**SerpApi limitation:** 100 searches/month = roughly 4–5 full runs (25 cities × 1–2 searches each). For personal use this is sufficient. Each search returns up to 20 results. For large cities you may miss some agents — acceptable given the free constraint.

---

## Project Structure

```
path_finder/
  backend/
    main.py              # FastAPI app, CORS, router registration
    config.py            # env var loading (pydantic-settings)
    database.py          # SQLite setup, job table creation
    models.py            # Pydantic request/response models
    worker.py            # background job orchestration
    services/
      serpapi.py         # SerpApi data acquisition
      sheets.py          # Google Sheets API v4
      routing.py         # OpenRouteService TSP
      email_sender.py    # SendGrid email
    routes/
      generate.py        # POST /api/generate
      status.py          # GET /api/status/{job_id}
      jobs.py            # GET /api/jobs
  frontend/
    index.html
    style.css
    app.js
  .env.example
  requirements.txt
  railway.toml           # or render.yaml
  PLAN.md
  CLAUDE.md
```

---

## Environment Variables

Create a `.env` file (never commit it). Use `.env.example` as the template.

```
# Data acquisition
SERPAPI_KEY=your_key_here

# Google (service account JSON as a single-line string)
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}

# Route optimization
OPENROUTESERVICE_API_KEY=your_key_here

# Email
SENDGRID_API_KEY=your_key_here
RECIPIENT_EMAIL=your@email.com

# App
SECRET_URL_TOKEN=your_random_string   # e.g. openssl rand -hex 16
```

---

## Phase 1 — Project Setup & Backend Skeleton

**Goal:** A running FastAPI server with job tracking, returning stub responses.

### Tasks

- [x] **1.1 Initialize project structure**
  - Create all directories listed in the Project Structure section above
  - Run: `cd backend && python -m venv venv && venv\Scripts\activate`
  - Install: `pip install fastapi uvicorn[standard] pydantic-settings python-dotenv aiohttp aiosqlite sendgrid google-auth google-auth-oauthlib google-api-python-client`
  - Create `requirements.txt`: `pip freeze > requirements.txt`
  - **Verify:** `uvicorn main:app --reload` starts without error. Visit `http://localhost:8000/docs` and see the Swagger UI.

- [x] **1.2 Create `config.py`**
  - Use `pydantic-settings` `BaseSettings` to load all env vars listed above
  - All fields optional with `None` default for now (they'll be required later)
  - **Verify:** `from config import settings; print(settings.model_dump())` prints keys without error

- [x] **1.3 Create `database.py`**
  - Use `aiosqlite` to create a `jobs` table on startup:
    ```sql
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      status TEXT NOT NULL,       -- pending | running | complete | failed
      progress TEXT,              -- human-readable current step
      result_json TEXT,           -- JSON blob on completion
      error TEXT,                 -- error message on failure
      created_at TEXT NOT NULL
    )
    ```
  - Expose async functions: `create_job(id, created_at)`, `update_job(id, **fields)`, `get_job(id)`, `list_jobs()`
  - Call table creation in FastAPI `lifespan` startup event
  - **Verify:** On server start, a `jobs.db` file appears in the backend directory

- [x] **1.4 Create `models.py`**
  - `GenerateRequest`: `cities: list[str]`, `start_address: str`, `end_address: str`, `route_mode: Literal["per_city", "all_cities"]`
  - `JobStatusResponse`: `id: str`, `status: str`, `progress: str | None`, `result: dict | None`, `error: str | None`
  - **Verify:** `from models import GenerateRequest` imports cleanly

- [x] **1.5 Create route handlers**
  - `routes/generate.py`: `POST /api/generate` — validate token from query param against `SECRET_URL_TOKEN`, create job row with `uuid4()` id and status `pending`, launch background task, return `{"job_id": id}`
  - `routes/status.py`: `GET /api/status/{job_id}` — fetch row from SQLite, return `JobStatusResponse`
  - `routes/jobs.py`: `GET /api/jobs` — return list of all jobs ordered by `created_at` desc
  - **Verify:** POST to `/api/generate?token=your_token` with a JSON body returns a `job_id`. GET `/api/status/{job_id}` returns `{"status": "pending"}`.

- [x] **1.6 Create stub `worker.py`**
  - `async def run_job(job_id, request)` — sets status to `running`, sleeps 3 seconds, sets status to `complete` with a dummy `result_json`
  - **Verify:** After posting to `/api/generate`, poll `/api/status/{job_id}` — it transitions from `pending` → `running` → `complete` within 5 seconds

- [x] **1.7 Create `.env.example`**
  - Copy all variable names from the Environment Variables section above with placeholder values
  - **Verify:** File exists and contains all variable names

---

## Phase 2 — Data Acquisition (SerpApi)

**Goal:** Given a city name, fetch insurance agent listings and return structured data.

### SerpApi Details
- Endpoint: `https://serpapi.com/search`
- Params: `engine=google_maps`, `q=insurance+agent`, `location={city}`, `type=search`, `api_key={key}`
- Returns up to 20 local results per search
- Each result contains: `title`, `address`, `phone`, `website`, `rating`, `place_id`
- **Cost:** 1 credit per search. Free tier = 100 credits/month.

### Tasks

- [x] **2.1 Create `services/serpapi.py`**
  - `async def fetch_agents(city: str) -> list[dict]`
  - Use `aiohttp.ClientSession` to call SerpApi
  - Parse `response["local_results"]` — each item: extract `title`, `address`, `phone`, `website`, `rating`, `place_id`
  - Return list of dicts with keys: `name`, `address`, `city`, `phone`, `website`, `rating`, `place_id`, `source`
  - Set `source = "serpapi"` on every record
  - Handle missing fields gracefully (use `.get()` with `""` default)
  - If `local_results` is missing or empty, return `[]` and log a warning
  - **Verify:** In a Python shell, `await fetch_agents("Phoenix, AZ")` returns a non-empty list with the correct fields

- [x] **2.2 Add deduplication logic**
  - In `services/serpapi.py`, add `deduplicate(agents: list[dict]) -> list[dict]`
  - Deduplicate by `place_id` — keep first occurrence
  - If `place_id` is empty string, deduplicate by exact `address` match
  - **Verify:** Pass a list with two identical `place_id` entries — only one is returned

- [x] **2.3 Wire data acquisition into `worker.py`**
  - Replace the stub sleep with: for each city in `request.cities`, call `fetch_agents(city)`, update job progress to `"Fetching agents in {city}... ({i}/{n})"`, collect all results
  - After all cities: deduplicate the master list across cities
  - Store raw agent list on the job object (in memory or temp file) for use in later phases
  - **Verify:** POST a generate request with 2 cities, poll status — progress messages update correctly, job reaches `complete`. Add a temporary log to print the agent count per city.

- [x] **2.4 Handle SerpApi errors**
  - If the API returns `{"error": "..."}`, catch it, set job status to `failed` with the error message
  - If the API key is missing, fail fast with a clear error: `"SERPAPI_KEY not configured"`
  - **Verify:** Use an invalid API key — job transitions to `failed` with a readable error

---

## Phase 3 — Google Sheets Integration

**Goal:** Write all fetched agents to a new Google Sheet, organized by city.

### One-Time Google Cloud Setup (do this before writing code)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. "path-finder")
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Name it (e.g. "path-finder-service"), click Create
6. On the service account page, go to **Keys → Add Key → JSON** — download the file
7. Open the JSON file — copy the entire contents as a single line into `GOOGLE_SERVICE_ACCOUNT_JSON` in your `.env`
8. Note the service account email (looks like `name@project.iam.gserviceaccount.com`)
9. In Google Drive, create a folder called "Path Finder Results" and share it with that service account email (Editor access)
10. Note the folder ID from the URL (the long string after `/folders/`)
11. Add `GOOGLE_DRIVE_FOLDER_ID=your_folder_id` to `.env` and `.env.example`

### Tasks

- [x] **3.1 Create `services/sheets.py`**
  - Load credentials from `GOOGLE_SERVICE_ACCOUNT_JSON` using `google.oauth2.service_account.Credentials.from_service_account_info()`
  - Scopes needed: `["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]`
  - Build the Sheets service: `googleapiclient.discovery.build("sheets", "v4", credentials=creds)`
  - Build the Drive service: `googleapiclient.discovery.build("drive", "v3", credentials=creds)`
  - **Verify:** `from services.sheets import get_sheets_service` imports without error

- [x] **3.2 Implement `create_spreadsheet(title: str, folder_id: str) -> str`**
  - Create a new spreadsheet via Drive API: `drive_service.files().create(body={"name": title, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [folder_id]})`
  - Return the spreadsheet ID
  - **Verify:** Call the function — a new spreadsheet appears in your Drive folder

- [x] **3.3 Implement `write_agents_to_sheet(spreadsheet_id: str, agents: list[dict], cities: list[str])`**
  - Rename "Sheet1" to "All Cities"
  - For each city in `cities`: create a new tab named after the city
  - Write header row to every tab: `["Agent Name", "Address", "City", "Phone", "Website", "Rating", "Latitude", "Longitude", "Source"]`
  - Write agent rows to the matching city tab and to "All Cities"
  - Use batch `values.batchUpdate` to write all data in one API call per tab (not one call per row)
  - Sort rows alphabetically by `Agent Name` within each tab before writing
  - **Verify:** After calling the function with test data, open the spreadsheet — all tabs exist with correct data

- [x] **3.4 Wire Sheets into `worker.py`**
  - After data acquisition completes, update job progress to `"Writing to Google Sheets..."`
  - Call `create_spreadsheet(f"Insurance Agents — {date}", folder_id)` to get a spreadsheet ID
  - Call `write_agents_to_sheet(...)` with all agents
  - Store the spreadsheet URL (`https://docs.google.com/spreadsheets/d/{id}`) in the job result
  - **Verify:** Run a full generate request — a populated Google Sheet appears in your Drive folder

- [x] **3.5 Handle Sheets errors**
  - If `GOOGLE_SERVICE_ACCOUNT_JSON` is missing or invalid, fail with: `"Google credentials not configured"`
  - If Drive folder doesn't exist, fail with: `"Google Drive folder not found — check GOOGLE_DRIVE_FOLDER_ID"`
  - **Verify:** Remove the env var and trigger a run — job fails with the correct message

---

## Phase 4 — Route Optimization (OpenRouteService)

**Goal:** Given a list of agent addresses, return an optimized driving order.

### OpenRouteService Details
- Sign up at [openrouteservice.org](https://openrouteservice.org) — free API key
- **Geocoding endpoint:** `https://api.openrouteservice.org/geocode/search?text={address}&api_key={key}` → returns lat/lng
- **Optimization endpoint:** `POST https://api.openrouteservice.org/optimization` — uses Vroom TSP solver
- Optimization input: `jobs` (each stop with lat/lng), `vehicles` (start/end coordinates), `shipments` (not needed here)
- Returns: ordered list of job IDs with estimated times and distances
- Limit: 50 stops per optimization request. For more, split into batches.

### Tasks

- [x] **4.1 Create `services/routing.py`**
  - `async def geocode_address(address: str) -> tuple[float, float] | None`
    - Call ORS geocoding API
    - Return `(longitude, latitude)` tuple (ORS uses lng, lat order)
    - Return `None` if address can't be geocoded; log a warning
  - **Verify:** `await geocode_address("123 Main St, Phoenix, AZ")` returns a (lng, lat) tuple

- [x] **4.2 Implement `async def optimize_route(start: tuple, end: tuple, stops: list[tuple]) -> list[int]`**
  - `start` and `end` are (lng, lat) tuples for the user's start/end address
  - `stops` is a list of (lng, lat) tuples for each agent
  - Build the ORS optimization payload:
    ```json
    {
      "vehicles": [{"id": 0, "profile": "driving-car", "start": [lng, lat], "end": [lng, lat]}],
      "jobs": [{"id": i, "location": [lng, lat]} for i, (lng, lat) in enumerate(stops)]
    }
    ```
  - Parse response: `solution.routes[0].steps` → filter steps where `type == "job"` → extract `job` field (the original index)
  - Return ordered list of original stop indices
  - **Verify:** Call with 5 test coordinates — returns a list of 5 indices in optimized order

- [x] **4.3 Implement batching for large stop lists**
  - If `len(stops) > 48` (leave 2 slots for start/end in the 50-stop limit):
    - Split stops into batches of 48
    - Run optimization on each batch independently
    - Concatenate results in order (imperfect but acceptable for free tier)
  - **Verify:** Call with 60 stops — function returns 60 indices without error

- [x] **4.4 Implement `async def build_routes(request, agents) -> dict`**
  - Geocode `request.start_address` and `request.end_address`
  - If `route_mode == "per_city"`:
    - For each city: geocode all agents in that city, optimize, return ordered stop list
    - Result: `{"Phoenix, AZ": [ordered agents], "Scottsdale, AZ": [ordered agents], ...}`
  - If `route_mode == "all_cities"`:
    - Geocode all agents across all cities, optimize as one list
    - Result: `{"all": [ordered agents]}`
  - For each ordered agent, store the geocoded lat/lng back onto the agent dict (for the Sheets `Latitude`/`Longitude` columns)
  - **Verify:** Run with 2 cities in `per_city` mode — result dict has 2 keys with ordered agent lists

- [x] **4.5 Wire routing into `worker.py`**
  - After Sheets step, update progress to `"Optimizing driving route..."`
  - Call `build_routes(request, agents)`
  - For each route, compute summary: stop count, estimated drive time (sum of durations from ORS response)
  - Store route summary and ordered stop list in job result
  - Update the Google Sheet `Latitude`/`Longitude` columns with geocoded coordinates
  - **Verify:** Full job run produces a route summary in the job result JSON

- [x] **4.6 Handle routing errors**
  - If geocoding the start/end address fails, fail the job: `"Could not geocode start address: {address}"`
  - If an agent address can't be geocoded, skip that agent (don't fail the whole job), log it
  - If ORS returns an error, log it and skip routing (job still completes with sheet but no route)
  - **Verify:** Use an invalid start address — job fails with the correct message

---

## Phase 5 — Email Notification (SendGrid)

**Goal:** When the job completes, send an HTML email with the sheet link and route summary.

### SendGrid Setup
1. Sign up at [sendgrid.com](https://sendgrid.com) — free tier is 100 emails/day
2. Go to **Settings → API Keys → Create API Key** (Full Access)
3. Go to **Settings → Sender Authentication → Single Sender Verification** and verify your sending email address
4. Add `SENDGRID_FROM_EMAIL=your_verified@email.com` to `.env` and `.env.example`

### Tasks

- [x] **5.1 Create `services/email_sender.py`**
  - `async def send_results_email(job_id: str, result: dict)`
  - Build HTML email body containing:
    - Subject: `f"Your Insurance Agent List is Ready — {city_count} Cities, {agent_count} Agents"`
    - Clickable link to the Google Sheet
    - Per-city summary table: city | agent count | estimated drive time
    - Ordered stop list for each route (agent name, address, phone as `<a href="tel:...">`)
    - Google Maps deep link for routes up to 8 stops: `https://www.google.com/maps/dir/{stop1}/{stop2}/...` (URL-encode each address)
    - For routes > 8 stops: omit the Maps deep link, just link to the Sheet
    - Timestamp at bottom: `Generated {datetime}`
  - Send via SendGrid Python SDK: `sendgrid.SendGridAPIClient(api_key).send(message)`
  - **Verify:** Call the function with test data — email arrives in your inbox with correct formatting

- [x] **5.2 Wire email into `worker.py`**
  - After routing completes, update progress to `"Sending email notification..."`
  - Call `send_results_email(job_id, result)`
  - If email fails, log the error but do NOT fail the job — the Sheet is still complete
  - Update job status to `complete` after email attempt (success or failure)
  - **Verify:** Full end-to-end run — email arrives with the Sheet link and route summary

- [x] **5.3 Handle email errors**
  - If `SENDGRID_API_KEY` is missing: log warning `"SendGrid not configured — skipping email"`, continue
  - If sender not verified: SendGrid returns 403 — log the error with instructions to verify sender
  - **Verify:** Remove API key — job completes successfully with a log warning, no crash

---

## Phase 6 — Frontend

**Goal:** A clean, mobile-first single-page web app that calls the backend and shows progress.

### Tasks

- [x] **6.1 Create `frontend/index.html`**
  - Form fields:
    - City input: text field + "Add City" button → renders a list of city chips with X to remove
    - Starting address: text input
    - Ending address: text input + checkbox "Same as starting address" (hides the field when checked)
    - Route mode: toggle button group — "Per City" | "All Cities"
    - "Generate" button
  - Below the form: a status section (hidden until job starts)
    - Progress message (e.g. "Fetching agents in Phoenix...")
    - Animated spinner
  - Results section (hidden until complete):
    - Link to Google Sheet (large, prominent button)
    - Summary: X cities, Y agents found
    - Per-city agent counts
    - Route summary (drive time, stop count)
  - Error section (hidden unless failed): shows error message in red with a "Try Again" button
  - **Verify:** Open in a mobile browser — all fields are visible and usable without horizontal scrolling

- [x] **6.2 Create `frontend/style.css`**
  - Mobile-first layout (max-width: 480px centered)
  - Font: system-ui or Inter from Google Fonts
  - City chips: rounded pill shape with X button, wraps to multiple lines
  - "Generate" button: full-width, prominent color (blue or green), disabled state while job runs
  - Progress section: spinner animation + left-aligned progress text
  - Results "Open Sheet" button: full-width, green, large tap target
  - Error text: red, clear
  - **Verify:** Open in Chrome DevTools mobile view (iPhone SE) — no layout breaks

- [x] **6.3 Create `frontend/app.js`**
  - `addCity()`: adds a city to the list, renders it as a chip
  - `removeCity(name)`: removes a city chip
  - `toggleSameAddress()`: shows/hides end address field
  - `submitForm()`:
    - Validates: at least 1 city, start address not empty
    - POSTs to `{BACKEND_URL}/api/generate?token={SECRET_URL_TOKEN}` with JSON body
    - Stores `job_id` from response
    - Shows progress section, starts polling
  - `pollStatus(job_id)`:
    - Calls `GET {BACKEND_URL}/api/status/{job_id}` every 4 seconds
    - Updates progress message text on each poll
    - On `complete`: stops polling, shows results section with data from `result`
    - On `failed`: stops polling, shows error section with the error message
  - Set `BACKEND_URL` and `SECRET_URL_TOKEN` as constants at the top of the file — these will be replaced with env var injection at deploy time
  - **Verify:** Open the page, submit a real request, watch the progress update live, results appear on completion

- [x] **6.4 Add CORS to the backend**
  - In `main.py`, add `CORSMiddleware` allowing the Vercel frontend origin
  - During development, allow `*` origin; restrict to the Vercel URL after deploy
  - **Verify:** Browser console shows no CORS errors when the frontend calls the backend

- [x] **6.5 Add basic rate limiting**
  - In `routes/generate.py`, track the last job creation time in memory (a module-level dict keyed by IP)
  - If a request comes from the same IP within 5 minutes of the last job, return HTTP 429 with message: `"A job is already running. Please wait before generating again."`
  - **Verify:** Submit two generate requests in quick succession from the browser — second returns 429

---

## Phase 7 — Integration Testing

**Goal:** Verify the full pipeline end-to-end before deploying.

### Tasks

- [ ] **7.1 Full happy-path test**
  - Fill in 2–3 real cities, a real start/end address, route mode "Per City"
  - Click Generate
  - Expected: progress updates through each step, email arrives, Sheet has correct tabs and data, job shows `complete`
  - **Verify:** Check all of the above manually. Confirm the Sheet URL in the email opens correctly.

- [ ] **7.2 "All Cities" route mode test**
  - Same as 7.1 but select "All Cities Combined"
  - **Verify:** Route result is a single ordered list across all input cities; email reflects this

- [ ] **7.3 "Same as start" checkbox test**
  - Check "Same as starting address" for the end address
  - **Verify:** Backend receives the same address for both `start_address` and `end_address`, route starts and ends at the same point

- [ ] **7.4 Error recovery test**
  - Enter a fake/unrecognizable city name (e.g. "Zxqrp, AZ")
  - **Verify:** Job completes with 0 agents for that city, does not crash; email and Sheet still generate for valid cities

- [ ] **7.5 Missing agent address test**
  - Manually test with a SerpApi result that has an empty address field (mock it if necessary)
  - **Verify:** Agent is included in the Sheet with blank address; route optimization skips it without crashing

- [ ] **7.6 Large city test**
  - Include one known large city (e.g. "Los Angeles, CA")
  - **Verify:** All returned agents are deduplicated; if > 48, batching engages without error

---

## Phase 8 — Deployment

**Goal:** Both services deployed, accessible from a phone, with all secrets in environment variables.

### Backend Deployment (Railway)

- [ ] **8.1 Create `railway.toml`**
  ```toml
  [build]
  builder = "nixpacks"

  [deploy]
  startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
  healthcheckPath = "/health"
  ```
  - Add a `/health` endpoint to `main.py`: returns `{"status": "ok"}`
  - **Verify:** `railway.toml` is present and valid

- [ ] **8.2 Deploy backend to Railway**
  - Sign up at [railway.app](https://railway.app)
  - Create a new project → deploy from GitHub (push the repo first) or use the Railway CLI
  - Set all environment variables from `.env` in Railway's dashboard (Variables tab)
  - Note the public URL (e.g. `https://path-finder-backend.up.railway.app`)
  - **Verify:** Visit `{BACKEND_URL}/health` in a browser — returns `{"status": "ok"}`

- [ ] **8.3 Update CORS in `main.py`**
  - Replace `*` origin with the specific Vercel URL after frontend is deployed
  - **Verify:** No CORS errors in browser after full deploy

### Frontend Deployment (Vercel)

- [ ] **8.4 Prepare frontend for deploy**
  - In `frontend/app.js`, replace hardcoded `BACKEND_URL` and `SECRET_URL_TOKEN` constants with values injected at build time
  - The simplest approach: use Vercel environment variables and a build step that runs `sed` to replace placeholder strings — or just hardcode them since this is a personal tool with no sensitive frontend value (the token only prevents accidental double-runs, not real auth)
  - **Verify:** The frontend correctly points to the Railway backend URL

- [ ] **8.5 Deploy frontend to Vercel**
  - Sign up at [vercel.com](https://vercel.com)
  - Import the GitHub repo, set root directory to `frontend/`
  - No build command needed for plain HTML/CSS/JS — Vercel serves static files directly
  - Note the Vercel URL (e.g. `https://path-finder.vercel.app`)
  - **Verify:** Visit the Vercel URL on a phone — the form loads and is usable

- [ ] **8.6 End-to-end smoke test on deployed system**
  - On a real phone, open the Vercel URL
  - Submit a real 2-city request
  - **Verify:** Progress updates appear, email arrives, Sheet is populated correctly

---

## Phase 9 — Polish (do after everything above works)

- [ ] **9.1 Real-time progress via polling refinement**
  - If the backend is cold-starting (Railway free tier sleeps after inactivity), the first poll may take 15–30 seconds
  - Show a "Waking up server..." message if the first poll takes > 10 seconds
  - **Verify:** Wait for Railway to sleep (15 min idle), then submit a request — the "waking up" message appears

- [ ] **9.2 Past jobs list**
  - Add a collapsible "Past Runs" section at the bottom of the page
  - On page load, fetch `GET /api/jobs` and render: date, cities, agent count, Sheet link, status
  - **Verify:** After 2 completed runs, both appear in the list with working Sheet links

- [ ] **9.3 Input validation improvements**
  - Prevent duplicate cities (case-insensitive check before adding chip)
  - Trim whitespace from city names and addresses before sending
  - Show character count for city chips if > 10 cities
  - **Verify:** Adding "phoenix, AZ" after "Phoenix, AZ" is blocked with a visible message

- [ ] **9.4 Mobile UX refinements**
  - After tapping Generate, scroll the page to the progress section automatically
  - Make the Sheet link button open in a new tab (`target="_blank"`)
  - On completion, vibrate the phone once if `navigator.vibrate` is available
  - **Verify:** Test each behavior on a real phone

---

## Completion Checklist

This project is complete when:

- [ ] A real user (non-technical) can open the Vercel URL on their phone, enter cities and addresses, and tap Generate
- [ ] Within 5–15 minutes, an email arrives with a Google Sheet link and route summary
- [ ] The Google Sheet has correct data organized by city tab
- [ ] The route in the email is in an optimized driving order
- [ ] All services run on free tiers with $0/month infrastructure cost
- [ ] No API keys or secrets appear in the codebase or git history

---

## How to Update This Plan

When a task is completed, check off the box: change `- [ ]` to `- [x]`. If you discover that a task needs to be changed, update it in place — don't add a new task below it. If a new task is discovered during implementation, add it to the appropriate phase.
