import asyncio
import json
import logging

from database import update_job
from models import GenerateRequest
from services.email_sender import send_results_email
from services.routing import build_routes, geocode_agents
from services.serpapi import deduplicate, fetch_agents
from services.sheets import create_and_populate_sheet

logger = logging.getLogger(__name__)


async def run_job(job_id: str, request: GenerateRequest, test_mode: bool = False):
    try:
        await update_job(job_id, status="running", progress="Starting job...")
        logger.info("Job %s started", job_id)

        # --- Phase 2: data acquisition ---
        all_agents: list[dict] = []
        city_counts: dict[str, int] = {}
        failed_cities: list[str] = []
        for i, city in enumerate(request.cities, 1):
            await update_job(job_id, progress=f"Fetching agents in {city}... ({i}/{len(request.cities)})")
            try:
                city_agents = await fetch_agents(city)
                city_counts[city] = len(city_agents)
                all_agents.extend(city_agents)
                logger.info("Fetched %d agents for %s", len(city_agents), city)
            except Exception as e:
                logger.warning("Failed to fetch agents for %s (skipping): %s", city, e)
                failed_cities.append(city)
                city_counts[city] = 0

        agents = deduplicate(all_agents)
        logger.info("Total after dedup: %d agents across %d cities", len(agents), len(request.cities))

        # --- Phase 4a: geocode agents (before sheet write so lat/lng lands in spreadsheet) ---
        await update_job(job_id, progress="Geocoding agent addresses...")
        await geocode_agents(agents)

        # --- Phase 3: Google Sheets ---
        await update_job(job_id, progress="Writing to Google Sheets...")
        sheet_url = await asyncio.to_thread(create_and_populate_sheet, agents, request.cities, test_mode)
        logger.info("Sheet written: %s", sheet_url)

        # --- Phase 4b: route optimization ---
        await update_job(job_id, progress="Optimizing driving route...")
        route_warning: str | None = None
        try:
            routes = await build_routes(request, agents)
            logger.info("Routes built: %s", list(routes.keys()))
        except Exception as e:
            logger.warning("Route optimization failed, continuing without routes: %s", e)
            routes = {}
            route_warning = "Route optimization failed — agents are listed in search order."

        # Build per-route summary (duration in minutes, rounded)
        route_summary: dict[str, dict] = {}
        for key, route in routes.items():
            route_summary[key] = {
                "stop_count": route["stop_count"],
                "duration_minutes": round(route["total_duration_seconds"] / 60),
                "ordered_agents": [
                    {
                        "name": a.get("name", ""),
                        "address": a.get("address", ""),
                        "city": a.get("city", ""),
                    }
                    for a in route["ordered_agents"]
                ],
            }

        result = {
            "sheet_url": sheet_url,
            "city_count": len(request.cities),
            "agent_count": len(agents),
            "cities": request.cities,
            "city_counts": city_counts,
            "failed_cities": failed_cities,
            "routes": route_summary,
            "route_warning": route_warning,
        }

        # --- Phase 5: email ---
        await update_job(job_id, progress="Sending email notification...")
        try:
            await send_results_email(result, test_mode=test_mode)
        except Exception as e:
            logger.error("Email failed (job still complete): %s", e)

        await update_job(job_id, status="complete", progress="Done!", result_json=json.dumps(result))
        logger.info("Job %s complete", job_id)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        await update_job(job_id, status="failed", error=str(e))
