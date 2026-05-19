# path_finder Wiki Log

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
