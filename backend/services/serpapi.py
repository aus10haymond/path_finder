import logging

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

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


async def fetch_agents(city: str) -> list[dict]:
    if not settings.serpapi_key:
        raise RuntimeError("SERPAPI_KEY not configured")

    params = {
        "engine": "google_maps",
        "q": f"home insurance agent {city}",
        "type": "search",
        "api_key": settings.serpapi_key,
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(SERPAPI_URL, params=params) as resp:
            data = await resp.json()

    if "error" in data:
        raise RuntimeError(f"SerpApi error: {data['error']}")

    results = data.get("local_results", [])
    if not results:
        logger.warning("No results returned for city: %s", city)
        return []

    agents = []
    skipped = 0
    for r in results:
        if not _is_relevant(r):
            skipped += 1
            logger.debug("Skipped auto-only listing: %s (%s)", r.get("title"), r.get("type"))
            continue
        agents.append({
            "name":     r.get("title", ""),
            "address":  r.get("address", ""),
            "city":     city,
            "phone":    r.get("phone", ""),
            "website":  r.get("website", ""),
            "rating":   r.get("rating", ""),
            "place_id": r.get("place_id", ""),
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
