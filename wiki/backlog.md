---
type: backlog
updated: 2026-05-19
---

# path_finder Backlog

Open issues and known problems. This is the source of truth for project-level issues; the portfolio backlog (`wiki/backlog.md`) surfaces the highest-priority item. Update when issues are resolved or new ones are discovered, and append to `log.md`.

→ [[wiki/projects/path_finder|Portfolio health page]]

## Open

_Nothing open._

## Resolved

- **[2026-05-19] Suite/unit addresses failing geocoding** — added `_strip_suite()` regex fallback as a third tier in `geocode_address()`; strips `Ste`, `Bldg`, `#`, `Unit`, etc. and retries Nominatim; resolved 13/13 failing addresses in the triggering run
- **[2026-05-19] SECRET_URL_TOKEN moved out of source** — token now injected server-side via Jinja2 template from `settings.secret_url_token`; hardcoded value removed from `frontend/app.js`
- **[2026-05-19] Route optimization silent failure fixed** — `build_routes` now re-raises on error; `worker.py` catches it and sets `route_warning` in job result; UI displays the warning message
- **[2026-05-19] Test suite added** — 47 tests across `serpapi`, `routing`, `email_sender`, `sheets` services; run with `.\venv\Scripts\python.exe -m pytest tests/ -v` from `backend/`
- **[2026-05-19] Render deploy 500 fixed** — `TemplateResponse` updated to Starlette keyword-argument API; old positional form caused Jinja2 LRU cache `TypeError` on Python 3.14
- **[2026-05-19] /api/test endpoint added** — full pipeline test mode bypassing rate limit; uses `TEST_GOOGLE_SPREADSHEET_ID` and `TEST_RECIPIENT_EMAIL` from env
