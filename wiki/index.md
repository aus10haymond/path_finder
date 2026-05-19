---
type: index
updated: 2026-05-19
---

# path_finder Wiki Index

→ [[wiki/projects/path_finder|Portfolio health page →]]

## Planning

- [[path_finder/wiki/roadmap|roadmap.md]] — 4-phase plan; Phase 1 done, Phase 2 next
- [[path_finder/wiki/backlog|backlog.md]] — open issues and known problems (SECRET_URL_TOKEN blocker)

## Runs

_No pages yet. Create a page here after each real run._
- Format: `runs/{YYYY-MM-DD}.md` — cities searched, agent count, route stops, email delivery, any failures

## Config

_No pages yet. Suggested first pages:_
- `config/api_decisions.md` — SerpApi chosen over Outscraper/Google Places; OpenRouteService chosen over Google Maps Routes — rationale and trade-offs
- `config/rate_limits.md` — SerpApi and OpenRouteService rate limits observed in practice; geocoding semaphore tuning

## Findings

_No pages yet. Suggested first pages:_
- `findings/dedup_patterns.md` — deduplication hit rate by city type; place_id vs address dedup behavior
- `findings/large_city_tiling.md` — geo-tiling behavior for cities like Phoenix, results per tile, overlap handling
