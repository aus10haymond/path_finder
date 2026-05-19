---
type: schema
updated: 2026-05-19
---

# path_finder Wiki Schema

Read this before any wiki operation in this project. Domain: insurance agent lead generation, SerpApi data acquisition, Google Sheets integration, route optimization.

**Vault root:** `Projects/` · **Timezone:** UTC+7

## Directory Layout

```
path_finder/wiki/
├── SCHEMA.md            # This file
├── index.md             # Catalog of all pages in this wiki
├── log.md               # Append-only activity log
├── roadmap.md           # Phase plan and current next step
├── backlog.md           # Open issues and known problems
├── runs/                # Per-run results (cities searched, leads found, route quality)
├── config/              # API choices made, design decisions, known limitations
└── findings/            # Patterns in insurance agent data, deduplication edge cases
```

## Frontmatter

```yaml
---
type: roadmap | backlog | run | config | finding
tags: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

## What Belongs Where

| Dir | Contents |
|---|---|
| `runs/` | Per-run summaries: cities searched, agent count before/after dedup, route stop count, email delivery result, any pipeline failures |
| `config/` | API decisions made (SerpApi vs alternatives, OpenRouteService vs Google Maps), known rate limits hit, environment variable reference, design decisions from `insurance_agent_system_architecture.md` that were resolved during implementation |
| `findings/` | Patterns in insurance agent data quality by city size (large city tiling behavior, dedup hit rate by city), SerpApi result reliability, routing accuracy observations |

## Wikilink Conventions

| Target | Syntax |
|---|---|
| Portfolio health page | `[[wiki/projects/path_finder]]` |
| Within this wiki | `[[path_finder/wiki/runs/2026-05-run]]` |

## When to Update the Portfolio Health Page

Update `Projects/wiki/projects/path_finder.md` after a session when:
- A new data source or route optimizer added
- Pipeline architecture changed
- Phase milestone completed (MVP → Phase 2 → Phase 3 → Phase 4)
- Critical bug found or resolved
- Health score would change by ≥ 1 point

## Operations

**After a run:**
1. Create page in `runs/` (e.g. `runs/2026-05-18.md`) — cities, lead counts, route stops, any failures
2. If a data quality pattern was noticed, update or create a page in `findings/`
3. Append to `log.md`: `## [YYYY-MM-DD] ingest | Run: {cities}`

**After a config or API decision:**
1. Create or update relevant page in `config/`
2. Append to `log.md`

**Update roadmap or backlog:**
1. Open `roadmap.md` — mark completed phases Done, update the Next Step and Blocker lines
2. Open `backlog.md` — close resolved issues (move to Resolved), add new ones under Open
3. Append to `log.md`: `## [YYYY-MM-DD] update | Roadmap/backlog updated`

**Lint:**
- Check `runs/` — do entries note any recurring pipeline failures worth fixing?
- Check `config/` — do API choice docs reflect the current implementation?
