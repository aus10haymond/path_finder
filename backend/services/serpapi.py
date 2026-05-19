import asyncio
import logging

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"
_ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"

# Trigger tiling when initial search returns this many results (likely saturated)
_SATURATION_THRESHOLD = 18

# (dlat, dlng) offsets for tile centers relative to city center.
# Each ~4–6 km in cardinal directions covers a full metro area with 1 initial + 4 tile searches.
_TILE_OFFSETS: list[tuple[float, float]] = [
    (0.04,  0.0),   # N (~4.5 km)
    (-0.04, 0.0),   # S
    (0.0,   0.06),  # E (~5 km at mid-latitudes)
    (0.0,  -0.06),  # W
]

# Google Maps category strings that are exclusively auto/vehicle insurance.
# General "Insurance agency" is NOT in this list — those offices typically
# sell home, renters, and flood policies alongside auto.
_AUTO_ONLY_TYPES = {
    "auto insurance agency",
    "car insurance agency",
    "vehicle insurance agency",
    "motorcycle insurance agency",
}

# If a business name contains any of these phrases it's treated as auto-only
# unless the name also contains a home-related word.
_CAR_NAME_PHRASES = {"auto insurance", "car insurance", "vehicle insurance", "truck insurance", "health insurance", "motorcycle insurance", "rv insurance", "boat insurance", "atv insurance", "classic car insurance",}
_HOME_NAME_WORDS = {"home", "homeowner", "homeowners", "property", "flood", "renters", "dwelling", "house",}


def _is_relevant(result: dict) -> bool:
    """Return False for listings that are clearly auto/vehicle-only."""
    business_type = result.get("type", "").lower().strip()
    name = result.get("title", "").lower()

    if business_type in _AUTO_ONLY_TYPES:
        return False

    # Name explicitly says "auto/car insurance" with no home-related context
    has_car_phrase = any(phrase in name for phrase in _CAR_NAME_PHRASES)
    has_home_word = any(word in name for word in _HOME_NAME_WORDS)
    if has_car_phrase and not has_home_word:
        return False

    return True


async def _geocode_city(session: aiohttp.ClientSession, city: str) -> tuple[float, float] | None:
    """Return (lat, lng) for a city name using ORS, or None on failure."""
    try:
        async with session.get(
            _ORS_GEOCODE_URL,
            params={"text": city, "size": 1, "api_key": settings.openrouteservice_api_key},
        ) as resp:
            data = await resp.json()
        features = data.get("features", [])
        if not features:
            return None
        coords = features[0]["geometry"]["coordinates"]  # [lng, lat]
        return float(coords[1]), float(coords[0])  # (lat, lng)
    except Exception as e:
        logger.debug("City geocoding failed for '%s': %s", city, e)
        return None


async def _search_tile(
    session: aiohttp.ClientSession,
    city: str,
    lat: float,
    lng: float,
) -> list[dict]:
    """Run one SerpApi search centered at (lat, lng). Returns raw local_results."""
    params = {
        "engine": "google_maps",
        "q": f"home insurance agent {city}",
        "type": "search",
        "ll": f"@{lat:.6f},{lng:.6f},13z",
        "api_key": settings.serpapi_key,
    }
    try:
        async with session.get(SERPAPI_URL, params=params) as resp:
            data = await resp.json()
        if "error" in data:
            logger.warning("SerpApi tile error for '%s': %s", city, data["error"])
            return []
        return data.get("local_results", [])
    except Exception as e:
        logger.warning("SerpApi tile request failed for '%s': %s", city, e)
        return []


async def fetch_agents(city: str) -> list[dict]:
    if not settings.serpapi_key:
        raise RuntimeError("SERPAPI_KEY not configured")

    async with aiohttp.ClientSession() as session:
        # Initial search (no explicit location pin — Google localises by city name)
        params = {
            "engine": "google_maps",
            "q": f"home insurance agent {city}",
            "type": "search",
            "api_key": settings.serpapi_key,
        }
        async with session.get(SERPAPI_URL, params=params) as resp:
            data = await resp.json()

        if "error" in data:
            raise RuntimeError(f"SerpApi error: {data['error']}")

        all_raw: list[dict] = list(data.get("local_results", []))
        if not all_raw:
            logger.warning("No results returned for city: %s", city)
            return []

        # Geo-tiling: when the initial search is saturated AND ORS is available,
        # search N/S/E/W tiles around the city centre to surface more agents.
        if len(all_raw) >= _SATURATION_THRESHOLD and settings.openrouteservice_api_key:
            city_center = await _geocode_city(session, city)
            if city_center:
                lat, lng = city_center
                semaphore = asyncio.Semaphore(3)

                async def _do_tile(dlat: float, dlng: float) -> list[dict]:
                    async with semaphore:
                        return await _search_tile(session, city, lat + dlat, lng + dlng)

                tile_results = await asyncio.gather(
                    *[_do_tile(dlat, dlng) for dlat, dlng in _TILE_OFFSETS],
                    return_exceptions=True,
                )
                extra = sum(len(r) for r in tile_results if isinstance(r, list))
                for tr in tile_results:
                    if isinstance(tr, list):
                        all_raw.extend(tr)
                logger.info("Geo-tiled '%s': %d additional raw results", city, extra)

    # Filter and deduplicate by place_id within this city.
    # Cross-city dedup (by address) is handled later in worker.py.
    agents: list[dict] = []
    skipped = 0
    seen_place_ids: set[str] = set()

    for r in all_raw:
        if not _is_relevant(r):
            skipped += 1
            logger.debug("Skipped auto-only listing: %s (%s)", r.get("title"), r.get("type"))
            continue
        pid = r.get("place_id", "")
        if pid and pid in seen_place_ids:
            continue
        if pid:
            seen_place_ids.add(pid)
        agents.append({
            "name":     r.get("title", ""),
            "address":  r.get("address", ""),
            "city":     city,
            "phone":    r.get("phone", ""),
            "website":  r.get("website", ""),
            "rating":   r.get("rating", ""),
            "place_id": pid,
            "source":   "serpapi",
        })

    logger.info("Fetched %d agents for %s (%d auto-only skipped)", len(agents), city, skipped)
    return agents


def deduplicate(agents: list[dict]) -> list[dict]:
    seen_place_ids: set[str] = set()
    seen_addresses: set[str] = set()
    unique: list[dict] = []

    for agent in agents:
        pid = agent.get("place_id", "")
        addr = agent.get("address", "")

        if pid:
            if pid in seen_place_ids:
                continue
            seen_place_ids.add(pid)
        else:
            if addr and addr in seen_addresses:
                continue
            if addr:
                seen_addresses.add(addr)

        unique.append(agent)

    return unique
