# path_finder Wiki Log

## [2026-05-19] fix | Google Maps links use configured start address as origin
`worker.py` now includes `start_address` and `end_address` in the job result dict. `mapsLinks()` in `app.js` and `_maps_links()` in `email_sender.py` now prepend `start_address` to the first segment URL and append `end_address` to the last. Previously all Maps /dir/ links started from stop #1 instead of the user's configured starting point.

## [2026-05-19] fix | Suite/unit stripping for unresolvable addresses
Added `_strip_suite()` as a third geocoding tier in `routing.py`. When both ORS and Nominatim fail on a full address, the function strips suite/unit designators (`Ste`, `Suite`, `STE`, `Bldg`, `Building`, `Unit`, `#`, etc.) via regex and retries Nominatim with the simplified street address. This resolved 13 misses in a 94-agent run — all were suite-qualified addresses in Gilbert and Mesa that Nominatim couldn't match verbatim but resolved cleanly at the street level.

## [2026-05-19] fix | Nominatim fallback for ORS geocoding misses
ORS geocoding (`/geocode/search`) returned no results for valid US addresses (e.g. "1679 E Beretta Pl, Chandler, AZ 85286"), causing route optimization to abort. Added `_nominatim_geocode()` as a fallback: `geocode_address()` now tries ORS first, then Nominatim (OpenStreetMap) on a miss. A module-level `asyncio.Lock` serializes Nominatim calls with a 1-second gap to comply with Nominatim's usage policy. Fixes both start-address failures (which were fatal) and improves agent geocoding coverage (9 misses in the triggering run).

## [2026-05-19] feat | Test mode UI + README
Added `?test=1` query-param support to `frontend/app.js`: when present, posts to `/api/test` instead of `/api/generate` and renders an amber "TEST MODE" banner. Token is still appended automatically. Created `README.md` at project root covering setup, env vars, test mode, and phase status.

## [2026-05-19] feat+fix | /api/test endpoint; Starlette Python 3.14 TemplateResponse fix
Added `POST /api/test` route (`backend/routes/test_route.py`) — runs the full pipeline against `TEST_GOOGLE_SPREADSHEET_ID` and `TEST_RECIPIENT_EMAIL`, bypasses the 300s IP rate limit, prefixes email subject with `[TEST]`, returns `{"job_id": ..., "test_mode": true}`. Threaded `test_mode` as an explicit bool param through `run_job`, `create_and_populate_sheet`, and `send_results_email` (safe for concurrent jobs, no global state mutation). Fixed Render deploy 500: `TemplateResponse` call in `main.py` updated to modern Starlette keyword-argument API (`request=`, `name=`, `context=`) — old positional form caused Jinja2 LRU cache `TypeError: unhashable type: dict` on Python 3.14.

## [2026-05-19] feat | Google Maps deep-links for route results
Added _maps_links() to email_sender.py: segments any-length route into overlapping chunks of ≤9 stops with shared boundary stops for continuity; email now renders labelled segment links for long routes instead of the old hard cap at 8. Frontend: mapsLinks() in app.js mirrors the logic, placing .btn-maps buttons above each route's stop list. 7 new _maps_links tests (coverage, continuity, boundaries). Total 78 tests.

## [2026-05-19] feat | Phase 3 complete — WebSocket, graceful failure, UI polish
Real-time progress: `ws_manager.py` (asyncio.Queue registry per job); `routes/ws.py` (WebSocket endpoint — sends current DB state immediately on connect, then pushes live updates, keepalive every 25 s); `database.py` pushes to ws_manager after every `update_job`. Frontend: WebSocket-first with automatic polling fallback on WS error/unexpected close. Graceful city failure: worker wraps per-city `fetch_agents` in try/except, collects `failed_cities` list in result — one bad city no longer fails the whole job. UI polish: 5-step progress indicator (Finding agents → Geocoding → Sheet → Route → Email) with active/done states; collapsible stop list (preview 8, "Show all N stops" link); `failed_cities` warning banner; `route-warning` styled callout; CSS for all new elements. 69 tests, all pass.

## [2026-05-19] feat | Phase 2 complete — geo-tiling + geographic clustering
Adaptive geo-tiling in `serpapi.py`: when initial search returns ≥18 results (saturated), geocodes the city via ORS and runs 4 additional tile searches (N/S/E/W, ~4–5 km offsets) with place_id dedup per city before global dedup in worker. Geographic k-means clustering in `routing.py`: for 150+ stops, clusters into groups of ~40 via `_kmeans_cluster` (deterministic, longitude-spread init), chains clusters via `_chain_clusters` (greedy nearest-neighbor from start), then optimizes each cluster with ORS. Added 16 new tests covering dist2, kmeans, chain, tiling trigger/skip/dedup. All 63 tests pass.

## [2026-05-19] fix+feat | SECRET_URL_TOKEN secured, routing failure surfaced, test suite added
Moved SECRET_URL_TOKEN from hardcoded `frontend/app.js` to Jinja2 server-side injection (from `settings.secret_url_token`). Route optimization now re-raises on failure; worker catches it and sets `route_warning` in result; UI displays message instead of silently empty route section. Added 47-test suite in `backend/tests/` covering serpapi (filtering, dedup, fetch), routing (geocoding, optimization), email_sender (duration, maps link, HTML), and sheets (row formatting, URL builder). Run: `.\venv\Scripts\python.exe -m pytest tests/ -v` from `backend/`.

## [2026-05-19] update | Added roadmap.md and backlog.md; updated SCHEMA.md and index.md
roadmap.md initialized with 4-phase plan (Phase 1 done, Phase 2 next; SECRET_URL_TOKEN blocker flagged). backlog.md initialized with 4 open issues. CLAUDE.md updated with wiki maintenance instructions.

## [2026-05-18] init | Wiki system initialized
Project wiki created. Initial health assessment from code review: 6/10. Core pipeline (SerpApi → dedup → Google Sheets → route → email) implemented. No test suite. Phase 1 MVP complete; Phases 2–4 not yet started.
