---
type: roadmap
updated: 2026-05-19
---

# path_finder Roadmap

4-phase development plan. Phase 1 MVP is complete and running. Update when a phase or blocker is resolved — mark it Done, update the Next Step, and append to `log.md`.

→ [[wiki/projects/path_finder|Portfolio health page]]

## Phase Status

| Phase | Status | Summary |
|---|---|---|
| 1 (MVP) | ✅ Done | SerpApi search → dedup → Google Sheets → route → SendGrid email; vanilla JS frontend |
| 2 | ✅ Done | Geo-tiling for large cities (adaptive 4-tile N/S/E/W search when saturated); geographic k-means clustering for 150+ route stops; SECRET_URL_TOKEN moved to server-side env var; route failure surfaced to UI; 63-test suite |
| 3 | ✅ Done | WebSocket real-time progress (WS-first, polling fallback); per-city graceful failure with `failed_cities` in result; 5-step progress indicator; collapsible stop lists; `route-warning` and `failed_cities` UI; 69-test suite |
| 4 (optional) | 🔜 Next | Run history, agent filtering, scheduling |

## Next Step

Phase 4 (optional): run history page, agent filtering by agency type, export to Google Maps/Waze, scheduling.
