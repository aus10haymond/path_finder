# path_finder

Personal-use lead generation tool for a damage restoration company owner. Given a list of cities, it finds local insurance agents via SerpApi, deduplicates by `place_id` and address, writes results to a Google Sheet, optimizes a driving route via OpenRouteService, and sends an email summary via SendGrid.

## Features

- City-by-city insurance agent search with auto/vehicle-only exclusion filter
- Adaptive geo-tiling for large cities (4-tile N/S/E/W search when results are saturated)
- Geographic k-means clustering for 150+ route stops
- Google Sheets output — one workbook per run, tabs per city + master "All Cities" tab
- Optimized driving route with Google Maps deep-links (segmented for long routes)
- SendGrid email summary with route details
- Real-time WebSocket progress with polling fallback
- Per-city graceful failure — one bad city doesn't abort the whole job
- IP-based rate limiting (300s cooldown)
- **Test mode** — same UI, bypasses rate limit, writes to test sheet and test email

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, asyncio, SQLite |
| Frontend | Vanilla JS, mobile-first |
| Search | SerpApi |
| Routing | OpenRouteService |
| Sheets | Google Sheets API v4 (service account) |
| Email | SendGrid |
| Hosting | Render |

## Setup

```bash
cd backend
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in all keys.

## Running locally

```bash
# Backend (from project root)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend — open frontend/index.html in a browser or serve statically
```

## Test mode

Append `?test=1` to the URL to activate test mode. The page shows an amber banner and posts to `/api/test`, which uses `TEST_GOOGLE_SPREADSHEET_ID` and `TEST_RECIPIENT_EMAIL` from the environment and bypasses the rate limit.

```
https://your-app.onrender.com?test=1
```

Protect the endpoint by setting `SECRET_URL_TOKEN` in the environment — the token is automatically appended to all requests by the frontend.

## Environment variables

| Variable | Purpose |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Sheets service account credentials |
| `SERPAPI_KEY` | SerpApi search |
| `OPENROUTESERVICE_API_KEY` | Route optimization |
| `SENDGRID_API_KEY` | Email delivery |
| `RECIPIENT_EMAIL` | Where to send results |
| `SECRET_URL_TOKEN` | Protects `/api/generate` and `/api/test` (optional) |
| `TEST_GOOGLE_SPREADSHEET_ID` | Sheet used in test mode |
| `TEST_RECIPIENT_EMAIL` | Email recipient in test mode |

## Tests

```bash
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -v
```

78 tests covering SerpApi filtering/dedup, routing, email, and sheets services.

## Development phases

| Phase | Status |
|---|---|
| 1 — MVP | ✅ Done |
| 2 — Geo-tiling + clustering | ✅ Done |
| 3 — WebSocket, graceful failure, UI polish | ✅ Done |
| 4 — Run history, filtering, scheduling | 🔜 Optional |
