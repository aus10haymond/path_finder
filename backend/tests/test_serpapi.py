from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.serpapi import _is_relevant, deduplicate, fetch_agents


# --- _is_relevant ---

class TestIsRelevant:
    def test_general_insurance_agency_is_kept(self):
        assert _is_relevant({"type": "Insurance agency", "title": "Smith Agency"})

    def test_auto_only_type_is_filtered(self):
        assert not _is_relevant({"type": "auto insurance agency", "title": "Quick Auto"})

    def test_car_insurance_type_is_filtered(self):
        assert not _is_relevant({"type": "car insurance agency", "title": "Bob's Car Insurance"})

    def test_auto_phrase_in_name_is_filtered(self):
        assert not _is_relevant({"type": "Insurance agency", "title": "Arizona Auto Insurance"})

    def test_car_phrase_with_home_context_is_kept(self):
        assert _is_relevant({"type": "Insurance agency", "title": "Auto and Homeowners Insurance Group"})

    def test_health_insurance_name_is_filtered(self):
        assert not _is_relevant({"type": "Insurance agency", "title": "Valley Health Insurance"})

    def test_empty_type_and_generic_name_is_kept(self):
        assert _is_relevant({"type": "", "title": "Local Insurance Office"})

    def test_motorcycle_insurance_type_is_filtered(self):
        assert not _is_relevant({"type": "motorcycle insurance agency", "title": "Rider's Choice"})


# --- deduplicate ---

class TestDeduplicate:
    def _agent(self, name, place_id="", address=""):
        return {"name": name, "place_id": place_id, "address": address}

    def test_deduplicates_by_place_id(self):
        agents = [
            self._agent("A", place_id="p1"),
            self._agent("B", place_id="p1"),
        ]
        result = deduplicate(agents)
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_deduplicates_by_address_when_no_place_id(self):
        agents = [
            self._agent("A", address="123 Main St"),
            self._agent("B", address="123 Main St"),
        ]
        result = deduplicate(agents)
        assert len(result) == 1

    def test_keeps_agents_with_different_place_ids(self):
        agents = [
            self._agent("A", place_id="p1"),
            self._agent("B", place_id="p2"),
        ]
        result = deduplicate(agents)
        assert len(result) == 2

    def test_agent_with_no_place_id_and_no_address_always_included(self):
        agents = [
            self._agent("A"),
            self._agent("B"),
        ]
        result = deduplicate(agents)
        assert len(result) == 2

    def test_place_id_takes_priority_over_address(self):
        agents = [
            self._agent("A", place_id="p1", address="123 Main"),
            self._agent("B", place_id="p2", address="123 Main"),
        ]
        result = deduplicate(agents)
        assert len(result) == 2

    def test_empty_input(self):
        assert deduplicate([]) == []


# --- fetch_agents ---

def _make_session(responses: list[dict]):
    """Build a mock aiohttp.ClientSession that returns each response dict in sequence."""
    call_count = 0

    def make_context(response):
        mock_resp = AsyncMock()
        mock_resp.json = AsyncMock(return_value=response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        return mock_resp

    contexts = [make_context(r) for r in responses]
    idx = 0

    def get_side_effect(*args, **kwargs):
        nonlocal idx
        ctx = contexts[min(idx, len(contexts) - 1)]
        idx += 1
        return ctx

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=get_side_effect)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _make_result(title, place_id, biz_type="Insurance agency"):
    return {"title": title, "type": biz_type, "place_id": place_id,
            "address": f"{title} St", "phone": "555", "website": "", "rating": 4.0}


@pytest.mark.asyncio
class TestFetchAgents:
    async def test_returns_filtered_agents(self):
        response = {
            "local_results": [
                _make_result("Smith Agency", "p1"),
                _make_result("Quick Auto", "p2", biz_type="auto insurance agency"),
            ]
        }
        session = _make_session([response])
        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            agents = await fetch_agents("Phoenix, AZ")

        assert len(agents) == 1
        assert agents[0]["name"] == "Smith Agency"

    async def test_raises_on_serpapi_error(self):
        session = _make_session([{"error": "Invalid API key"}])
        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            with pytest.raises(RuntimeError, match="SerpApi error"):
                await fetch_agents("Phoenix, AZ")

    async def test_returns_empty_list_when_no_results(self):
        session = _make_session([{"local_results": []}])
        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            agents = await fetch_agents("Nowhere, AZ")
        assert agents == []

    async def test_deduplicates_by_place_id_within_city(self):
        """Two results with same place_id yield one agent."""
        response = {
            "local_results": [
                _make_result("Smith Agency", "p1"),
                _make_result("Smith Agency Duplicate", "p1"),
            ]
        }
        session = _make_session([response])
        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            agents = await fetch_agents("Phoenix, AZ")
        assert len(agents) == 1

    async def test_geo_tiling_not_triggered_below_threshold(self):
        """Fewer than _SATURATION_THRESHOLD results → no tile searches."""
        results = [_make_result(f"Agent {i}", f"p{i}") for i in range(10)]
        response = {"local_results": results}

        session = _make_session([response])
        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            with patch("services.serpapi.settings") as mock_settings:
                mock_settings.serpapi_key = "key"
                mock_settings.openrouteservice_api_key = "ors-key"
                agents = await fetch_agents("Smalltown, AZ")

        # Only 1 get call (the initial search) — no tiles
        assert session.get.call_count == 1
        assert len(agents) == 10

    async def test_geo_tiling_triggered_at_saturation(self):
        """>=18 results with ORS key → geocode city + 4 tile searches."""
        saturated = [_make_result(f"Agent {i}", f"p{i}") for i in range(20)]
        geocode_response = {"features": [{"geometry": {"coordinates": [-112.0, 33.4]}}]}
        tile_response = {"local_results": [_make_result("Tile Agent", "p99")]}

        # Sequence: initial search, geocode, 4 tiles
        session = _make_session([
            {"local_results": saturated},   # initial
            geocode_response,               # geocode city
            tile_response,                  # tile N
            tile_response,                  # tile S
            tile_response,                  # tile E
            tile_response,                  # tile W
        ])

        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            with patch("services.serpapi.settings") as mock_settings:
                mock_settings.serpapi_key = "key"
                mock_settings.openrouteservice_api_key = "ors-key"
                agents = await fetch_agents("Phoenix, AZ")

        # Should have initial 20 + tile agent p99 (deduped from 4 tile responses)
        assert any(a["place_id"] == "p99" for a in agents)

    async def test_geo_tiling_skipped_without_ors_key(self):
        """Saturated results but no ORS key → no tiling."""
        saturated = [_make_result(f"Agent {i}", f"p{i}") for i in range(20)]
        session = _make_session([{"local_results": saturated}])

        with patch("services.serpapi.aiohttp.ClientSession", return_value=session):
            with patch("services.serpapi.settings") as mock_settings:
                mock_settings.serpapi_key = "key"
                mock_settings.openrouteservice_api_key = None
                agents = await fetch_agents("Phoenix, AZ")

        assert session.get.call_count == 1
        assert len(agents) == 20
