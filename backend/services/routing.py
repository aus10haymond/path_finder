import asyncio
import logging
import re

import aiohttp

from config import settings
from models import GenerateRequest

logger = logging.getLogger(__name__)

ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_OPTIMIZE_URL = "https://api.openrouteservice.org/optimization"
NOMINATIM_GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "path-finder-lead-tool/1.0"}

BATCH_SIZE = 48          # ORS optimization limit per request
CLUSTER_THRESHOLD = 150  # stop count that triggers geographic clustering
STOPS_PER_CLUSTER = 40   # target cluster size (keeps each cluster under BATCH_SIZE)


# Matches suite/unit designators and everything after them up to the next comma.
# Handles: Ste 101, Suite 129, STE 120, Bldg 6 Suite 129, #110, Unit 104 Ste 1
_SUITE_RE = re.compile(
    r"\s*,?\s*(?:Ste|Suite|STE|Bldg|Building|Unit|Apt|Apartment|Fl|Floor|#)\b.*?(?=,|$)",
    re.IGNORECASE,
)


def _strip_suite(address: str) -> str:
    return _SUITE_RE.sub("", address).strip().strip(",").strip()


_nominatim_lock = asyncio.Lock()


async def _nominatim_geocode(session: aiohttp.ClientSession, address: str) -> tuple[float, float] | None:
    """Fallback geocoder using Nominatim (OpenStreetMap). Returns (lng, lat) or None.
    Serializes requests with a 1-second gap to respect Nominatim's usage policy."""
    async with _nominatim_lock:
        try:
            async with session.get(
                NOMINATIM_GEOCODE_URL,
                params={"q": address, "format": "json", "limit": 1},
                headers=NOMINATIM_HEADERS,
            ) as resp:
                data = await resp.json()
            await asyncio.sleep(1)
            if not data:
                return None
            return float(data[0]["lon"]), float(data[0]["lat"])
        except Exception as e:
            logger.warning("Nominatim geocoding failed for '%s': %s", address, e)
            return None


async def geocode_address(session: aiohttp.ClientSession, address: str) -> tuple[float, float] | None:
    """Returns (longitude, latitude) or None if all geocoders fail. Tries ORS then Nominatim."""
    if not address.strip():
        return None
    try:
        async with session.get(
            ORS_GEOCODE_URL,
            params={"text": address, "size": 1, "api_key": settings.openrouteservice_api_key},
        ) as resp:
            data = await resp.json()
        features = data.get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
            return float(coords[0]), float(coords[1])
        logger.debug("ORS geocode miss for '%s', trying Nominatim", address)
    except Exception as e:
        logger.debug("ORS geocoding failed for '%s': %s — trying Nominatim", address, e)

    coords = await _nominatim_geocode(session, address)
    if coords is not None:
        return coords

    stripped = _strip_suite(address)
    if stripped != address:
        logger.debug("Retrying Nominatim without suite for '%s'", address)
        coords = await _nominatim_geocode(session, stripped)

    if coords is None:
        logger.warning("No geocode result for: %s", address)
    return coords


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


# ---------------------------------------------------------------------------
# Geographic clustering helpers (used for 150+ stops)
# ---------------------------------------------------------------------------

def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Squared Euclidean distance between two (lng, lat) points."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _kmeans_cluster(
    stops: list[tuple[float, float]],
    k: int,
    iterations: int = 15,
) -> list[list[int]]:
    """
    K-means clustering on (lng, lat) stop coordinates.
    Returns list of groups, each containing global stop indices.
    Initialises centroids spread evenly by longitude for deterministic results.
    """
    n = len(stops)
    k = min(k, n)

    # Spread initial centroids evenly across longitude range
    sorted_by_lng = sorted(range(n), key=lambda i: stops[i][0])
    step = max(1, n // k)
    centroids: list[tuple[float, float]] = [stops[sorted_by_lng[i * step]] for i in range(k)]

    clusters: list[list[int]] = []
    for _ in range(iterations):
        clusters = [[] for _ in range(k)]
        for i, stop in enumerate(stops):
            nearest = min(range(k), key=lambda c: _dist2(stop, centroids[c]))
            clusters[nearest].append(i)

        new_centroids: list[tuple[float, float]] = []
        for c in range(k):
            if clusters[c]:
                lngs = [stops[i][0] for i in clusters[c]]
                lats = [stops[i][1] for i in clusters[c]]
                new_centroids.append((sum(lngs) / len(lngs), sum(lats) / len(lats)))
            else:
                new_centroids.append(centroids[c])

        if new_centroids == centroids:
            break
        centroids = new_centroids

    return [c for c in clusters if c]


def _chain_clusters(
    clusters: list[list[int]],
    stops: list[tuple[float, float]],
    start: tuple[float, float],
) -> list[list[int]]:
    """
    Order clusters using greedy nearest-neighbour from the start point.
    Returns clusters in visitation order.
    """
    centroids = []
    for c in clusters:
        lngs = [stops[i][0] for i in c]
        lats = [stops[i][1] for i in c]
        centroids.append((sum(lngs) / len(lngs), sum(lats) / len(lats)))

    ordered: list[list[int]] = []
    remaining = list(range(len(clusters)))
    current = start

    while remaining:
        nearest = min(remaining, key=lambda i: _dist2(current, centroids[i]))
        ordered.append(clusters[nearest])
        current = centroids[nearest]
        remaining.remove(nearest)

    return ordered


# ---------------------------------------------------------------------------
# ORS optimization
# ---------------------------------------------------------------------------

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


async def _optimize_cluster(
    session: aiohttp.ClientSession,
    start: tuple[float, float],
    end: tuple[float, float],
    global_indices: list[int],
    all_stops: list[tuple[float, float]],
) -> tuple[list[int], int]:
    """Optimize one geographic cluster. Maps local ORS indices back to global stop indices."""
    cluster_stops = [all_stops[i] for i in global_indices]
    local_ordered, duration = await _optimize_batch(session, start, end, cluster_stops, 0)
    return [global_indices[li] for li in local_ordered], duration


async def optimize_route(
    start: tuple[float, float],
    end: tuple[float, float],
    stops: list[tuple[float, float]],
) -> tuple[list[int], int]:
    """
    Returns (ordered_stop_indices, total_duration_seconds).

    Strategy by stop count:
    - <= 48:  single ORS batch
    - 49-150: sequential batches (existing behaviour)
    - 150+:   k-means geographic clustering → per-cluster ORS → greedy cluster chaining
    """
    if not stops:
        return [], 0

    async with aiohttp.ClientSession() as session:
        if len(stops) <= BATCH_SIZE:
            return await _optimize_batch(session, start, end, stops, 0)

        if len(stops) <= CLUSTER_THRESHOLD:
            # Sequential batching for mid-range counts
            all_ordered: list[int] = []
            total_duration = 0
            for offset in range(0, len(stops), BATCH_SIZE):
                batch = stops[offset: offset + BATCH_SIZE]
                ordered, duration = await _optimize_batch(session, start, end, batch, offset)
                all_ordered.extend(ordered)
                total_duration += duration
            return all_ordered, total_duration

        # Geographic clustering for large stop counts
        k = max(2, len(stops) // STOPS_PER_CLUSTER)
        logger.info("Clustering %d stops into %d geographic groups", len(stops), k)
        clusters = _kmeans_cluster(stops, k)
        clusters = _chain_clusters(clusters, stops, start)

        all_ordered = []
        total_duration = 0
        for cluster_indices in clusters:
            ordered, duration = await _optimize_cluster(session, start, end, cluster_indices, stops)
            all_ordered.extend(ordered)
            total_duration += duration
        return all_ordered, total_duration


async def build_routes(request: GenerateRequest, agents: list[dict]) -> dict[str, dict]:
    """
    Geocode start/end and optimize routes.
    Returns dict keyed by city name (or "all") with ordered_agents, stop_count, total_duration_seconds.
    Raises on failure so worker.py can surface the error to the user.
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
        logger.warning("Route optimization failed: %s", e)
        raise
