# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal-use lead generation tool for a damage restoration company owner. Given a list of cities, it finds local insurance agents via SerpApi, deduplicates by `place_id` and address, writes results to a Google Sheet, optimizes a driving route via OpenRouteService, and sends an email summary via SendGrid. Mobile-first single-page frontend (vanilla JS) polling a FastAPI async backend. Job state persists in SQLite. Phase 1 MVP is complete and working; Phases 2–4 are not yet started.

## Commands

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Start the backend (from project root)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Open the frontend
# Open frontend/index.html in a browser, or serve statically
```

## Architecture

```
frontend/index.html + app.js
        |  POST /api/generate
        v
backend/routes/generate.py   — rate limiting (IP-based, 300s cooldown), creates job in SQLite
        |
        v
backend/worker.py            — background async job orchestration
        |
        |---> services/serpapi.py    — search + auto/vehicle insurance filter + dedup by place_id
        |---> services/sheets.py     — Google Sheets API v4 write (one sheet per run, tabs per city)
        |---> services/routing.py    — geocoding (aiohttp) + OpenRouteService route optimization
        └---> services/email_sender.py — SendGrid email notification
```

Jobs run in the background. Frontend polls `GET /api/status/{job_id}` every 4 seconds for progress.

## Data flow

1. User submits cities + start/end addresses via web form
2. Backend creates background job, returns `job_id`
3. Worker: SerpApi search per city → filter (exclude auto-only insurers) → deduplicate by `place_id` → write Google Sheet → optimize route → send email
4. Frontend shows progress and final links

## Google Sheet structure

- One workbook per run: `"Insurance Agents — [Date]"`
- Tabs: `"All Cities"` (master) + one tab per city
- Columns: `Agent Name | Business Name | Address | City | Phone | Website | Rating | Source`

## Environment variables

All in `.env` — never commit:
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Google Sheets + Gmail service account
- `SERPAPI_KEY` — SerpApi search API
- `OPENROUTESERVICE_API_KEY` — route optimization
- `SENDGRID_API_KEY` — email delivery
- `RECIPIENT_EMAIL` — where to send results

## Large city handling

For large cities, use geo-tiling: get city bounding box → divide into overlapping search circles → search each circle → merge and deduplicate by `place_id`. For 150+ route stops: cluster geographically, optimize within clusters, chain clusters in order.

## Key files

| Task | File |
|---|---|
| Background job orchestration | `backend/worker.py` |
| Insurance agent search + filtering | `backend/services/serpapi.py` |
| Google Sheets write | `backend/services/sheets.py` |
| Geocoding + route optimization | `backend/services/routing.py` |
| Email notification | `backend/services/email_sender.py` |
| Job creation + rate limiting | `backend/routes/generate.py` |
| Job status polling | `backend/routes/status.py` |
| Frontend UI | `frontend/index.html` + `frontend/app.js` |
| Pydantic models | `backend/models.py` |
| SQLite job tracking | `backend/database.py` |
| Settings | `backend/config.py` |
| Full system design | `insurance_agent_system_architecture.md` |

## Development phases

- **Phase 1 (MVP):** ✅ Complete — FastAPI + SerpApi + Google Sheets + email + basic frontend
- **Phase 2:** Route optimization enhancements (per-city and all-cities modes)
- **Phase 3:** Real-time progress (WebSocket), multiple data source fallback, mobile UI polish
- **Phase 4 (optional):** Run history, agent filtering, scheduling

## Wiki

This project has a wiki at `path_finder/wiki/`. Read `path_finder/wiki/SCHEMA.md` before any wiki operation.

**Directories:** `runs/` (per-run results), `config/` (API decisions, rate limits), `findings/` (data quality patterns, dedup behavior).

**After completing work in this project:**
- Update `wiki/roadmap.md` — mark completed phases/tasks Done, update the Next Step pointer
- Update `wiki/backlog.md` — close resolved issues, add newly discovered ones
- Append to `wiki/log.md`
- Update `Projects/wiki/projects/path_finder.md` if a threshold event occurred (new data source or route optimizer, pipeline phase completed, critical bug found or resolved, architecture changed). See `wiki/SCHEMA.md` for the full trigger list.
