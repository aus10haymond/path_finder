import asyncio
import logging

import aiohttp

from config import settings
from models import GenerateRequest

logger = logging.getLogger(__name__)

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_OPTIMIZE_URL = "https://api.openrouteservice.org/optimization"


async def geocode_address(session: aiohttp.ClientSession, address: str) -> tuple[float, float] | None:
    """Returns (longitude, latitude) or None if geocoding fails."""
    if not address.strip():
        return None
    try:
        async with session.get(
            ORS_GEOCODE_URL,
            params={"text": address, "size": 1, "api_key": settings.openrouteservice_api_key},
        ) as resp:
            data = await resp.json()
        features = data.get("features", [])
        if not features:
            logger.warning("No geocode result for: %s", address)
            return None
        coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
        return float(coords[0]), float(coords[1])
    except Exception as e:
        logger.warning("Geocoding failed for '%s': %s", address, e)
        return None


async def _geocode_agent(session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, agent: dict) -> None:
    full_address = f"{agent.get('address', '')}, {agent.get('city', '')}".strip(", ")
    async with semaphore:
        coords = await geocode_address(session, full_address)
    if coords:
        agent["lng"], agent["lat"] = coords
    else:
        agent["lng"], agent["lat"] = "", ""


async def geocode_agents(agents: list[dict]) -> None:
    """Geocode all agents concurrently (max 5 at a time), populating lat/lng in-place."""
    if not settings.openrouteservice_api_key:
        for agent in agents:
            agent["lng"], agent["lat"] = "", ""
        return

    semaphore = asyncio.Semaphore(5)
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[_geocode_agent(session, semaphore, a) for a in agents])


async def _optimize_batch(
    session: aiohttp.ClientSession,
    start: tuple[float, float],
    end: tuple[float, float],
    stops: list[tuple[float, float]],
    id_offset: int,
) -> tuple[list[int], int]:
    """Run ORS optimization on one batch. Returns (ordered_global_indices, duration_seconds)."""
    payload = {
        "vehicles": [
            {
                "id": 0,
                "profile": "driving-car",
                "start": list(start),
                "end": list(end),
            }
        ],
        "jobs": [
            {"id": id_offset + i, "location": list(coords)}
            for i, coords in enumerate(stops)
        ],
    }

    async with session.post(
        ORS_OPTIMIZE_URL,
        json=payload,
        headers={"Authorization": settings.openrouteservice_api_key, "Content-Type": "application/json"},
    ) as resp:
        data = await resp.json()

    if "error" in data:
        raise RuntimeError(f"ORS optimization error: {data['error']}")

    routes = data.get("routes", [])
    if not routes:
        return list(range(id_offset, id_offset + len(stops))), 0

    steps = routes[0].get("steps", [])
    ordered = [step["id"] for step in steps if step.get("type") == "job"]
    duration = routes[0].get("duration", 0)
    return ordered, int(duration)


async def optimize_route(
    start: tuple[float, float],
    end: tuple[float, float],
    stops: list[tuple[float, float]],
) -> tuple[list[int], int]:
    """
    Returns (ordered_stop_indices, total_duration_seconds).
    Handles batching automatically for > 48 stops.
    """
    if not stops:
        return [], 0

    BATCH_SIZE = 48
    async with aiohttp.ClientSession() as session:
        if len(stops) <= BATCH_SIZE:
            return await _optimize_batch(session, start, end, stops, 0)

        # Split into batches, optimize each independently, concatenate
        all_ordered: list[int] = []
        total_duration = 0
        for offset in range(0, len(stops), BATCH_SIZE):
            batch = stops[offset: offset + BATCH_SIZE]
            ordered, duration = await _optimize_batch(session, start, end, batch, offset)
            all_ordered.extend(ordered)
            total_duration += duration
        return all_ordered, total_duration


async def build_routes(request: GenerateRequest, agents: list[dict]) -> dict[str, dict]:
    """
    Geocode start/end and optimize routes.
    Returns dict keyed by city name (or "all") with ordered_agents, stop_count, total_duration_seconds.
    Falls back to unoptimized order and logs a warning if ORS fails.
    """
    if not settings.openrouteservice_api_key:
        logger.warning("OPENROUTESERVICE_API_KEY not configured — skipping route optimization")
        return {}

    # Geocode start and end addresses
    async with aiohttp.ClientSession() as session:
        start_coords = await geocode_address(session, request.start_address)
        end_coords = await geocode_address(session, request.end_address)

    if not start_coords:
        raise RuntimeError(f"Could not geocode start address: {request.start_address}")
    if not end_coords:
        raise RuntimeError(f"Could not geocode end address: {request.end_address}")

    # Filter agents that have valid coordinates
    def has_coords(a: dict) -> bool:
        return bool(a.get("lng")) and bool(a.get("lat"))

    try:
        if request.route_mode == "all_cities":
            geocoded = [a for a in agents if has_coords(a)]
            stops = [(a["lng"], a["lat"]) for a in geocoded]
            ordered_indices, duration = await optimize_route(start_coords, end_coords, stops)
            ordered_agents = [geocoded[i] for i in ordered_indices]
            return {
                "all": {
                    "ordered_agents": ordered_agents,
                    "stop_count": len(ordered_agents),
                    "total_duration_seconds": duration,
                }
            }
        else:  # per_city
            result: dict[str, dict] = {}
            agents_by_city: dict[str, list[dict]] = {city: [] for city in request.cities}
            for agent in agents:
                city = agent.get("city", "")
                if city in agents_by_city and has_coords(agent):
                    agents_by_city[city].append(agent)

            for city, city_agents in agents_by_city.items():
                if not city_agents:
                    result[city] = {"ordered_agents": [], "stop_count": 0, "total_duration_seconds": 0}
                    continue
                stops = [(a["lng"], a["lat"]) for a in city_agents]
                ordered_indices, duration = await optimize_route(start_coords, end_coords, stops)
                ordered_agents = [city_agents[i] for i in ordered_indices]
                result[city] = {
                    "ordered_agents": ordered_agents,
                    "stop_count": len(ordered_agents),
                    "total_duration_seconds": duration,
                }
            return result

    except Exception as e:
        logger.warning("Route optimization failed, returning unoptimized: %s", e)
        return {}
