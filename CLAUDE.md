# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Path Finder** (Insurance Agent Lead Finder) is a personal-use tool for a damage restoration company owner to find insurance agents across multiple cities, organize them into a Google Sheet, optimize a driving route to visit them, and email the results. The full system spec is in `insurance_agent_system_architecture.md`.

This project is currently in the **architecture/design phase** — no source code exists yet. The reference documents are:
- `insurance_agent_system_architecture.md` — full system design
- `insurance_agent_system_architecture.pdf` / `insurance_agent_diagrams.pdf` — visual diagrams

## Planned Stack

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI |
| Frontend | React (or plain HTML/CSS/JS) |
| Job queue | `asyncio` (or Celery + Redis if needed) |
| Database | SQLite (job tracking only) |
| Hosting | Vercel (frontend), Railway/Render (backend) |

## Architecture

```
[Mobile Web App]
      |
      v
[FastAPI Backend]
      |
      |---> [Data Acquisition Layer]   → agent data (Google Places / Outscraper / SerpApi)
      |---> [Google Sheets API v4]     → organizes results into spreadsheet
      |---> [Route Optimization API]   → OpenRouteService or Google Maps Routes API
      └---> [Gmail API / SendGrid]     → email notification on completion
```

**Key API endpoints (to build):**
```
POST /api/generate        — start a job; returns job_id immediately
GET  /api/status/{job_id} — poll for progress
GET  /api/jobs            — list past jobs
```

Jobs run in the background. The frontend polls `/api/status/{job_id}` (or uses WebSockets) for progress.

## Data Flow

1. User submits cities + start/end addresses + route mode via the web app
2. Backend creates a background job and returns `job_id`
3. Worker fetches agents per city → deduplicates → writes Google Sheet → optimizes route → sends email
4. Frontend polls status; shows "Done" with links when complete

**Google Sheet structure:**
- One workbook per run: `"Insurance Agents — [Date]"`
- Tabs: `"All Cities"` (master) + one tab per city
- Columns: `Agent Name | Business Name | Address | City | Phone | Website | Rating | Source`

## Key Design Decisions (unresolved)

These choices affect implementation — confirm before building each component:

1. **Data source:** Outscraper (easiest, ~$2–15/run) vs Google Places API (~$5–25/run, more control) vs SerpApi (free tier, 100 searches/month)
2. **Route optimizer:** OpenRouteService (free, 50 stops/request) vs Google Maps Routes API (25 stops, chains, more accurate)
3. **Email:** Gmail API (uses existing Gmail account) vs SendGrid (100 free/day)
4. **Frontend:** Single-page no-auth (secret URL as access control) vs history/saved cities

## Environment Variables

All API keys must be stored as env vars — never in code:
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Google Sheets + Gmail
- `OUTSCRAPER_API_KEY` / `SERPAPI_KEY` / `GOOGLE_PLACES_API_KEY` — data source
- `OPENROUTESERVICE_API_KEY` / `GOOGLE_MAPS_API_KEY` — route optimizer
- `RECIPIENT_EMAIL` — where to send results

## Large City Handling

For large cities, Google Places returns max 20 results per call. Use geo-tiling:
1. Get city bounding box
2. Divide into overlapping search circles
3. Search each circle, merge, deduplicate by place ID

For 150+ route stops: cluster geographically (k-means), optimize within clusters, chain clusters in order.

## Development Phases

- **Phase 1 (MVP):** FastAPI + one data source + Google Sheets + email + basic frontend
- **Phase 2:** Route optimization (per-city and all-cities modes)
- **Phase 3:** Real-time progress, multiple data sources with fallback, mobile UI polish
- **Phase 4 (optional):** Run history, agent filtering, scheduling
