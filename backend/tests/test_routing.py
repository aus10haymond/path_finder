from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.routing import (
    _chain_clusters,
    _dist2,
    _kmeans_cluster,
    geocode_address,
    geocode_agents,
    optimize_route,
)


def _make_session(json_response):
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=json_response)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# --- _dist2 ---

class TestDist2:
    def test_same_point_is_zero(self):
        assert _dist2((1.0, 2.0), (1.0, 2.0)) == 0.0

    def test_unit_distance(self):
        assert _dist2((0.0, 0.0), (1.0, 0.0)) == 1.0

    def test_diagonal(self):
        assert _dist2((0.0, 0.0), (3.0, 4.0)) == 25.0


# --- _kmeans_cluster ---

class TestKmeansCluster:
    def test_clusters_into_k_groups(self):
        # Two clearly separated clusters
        west = [(float(i), 33.0) for i in range(10)]
        east = [(float(i + 100), 33.0) for i in range(10)]
        stops = west + east

        clusters = _kmeans_cluster(stops, k=2)
        assert len(clusters) == 2
        sizes = sorted(len(c) for c in clusters)
        assert sizes == [10, 10]

    def test_all_same_point_gives_one_non_empty_cluster(self):
        stops = [(0.0, 0.0)] * 5
        clusters = _kmeans_cluster(stops, k=2)
        non_empty = [c for c in clusters if c]
        total_indices = sum(len(c) for c in non_empty)
        assert total_indices == 5

    def test_k_capped_at_n(self):
        stops = [(float(i), 0.0) for i in range(3)]
        clusters = _kmeans_cluster(stops, k=10)
        non_empty = [c for c in clusters if c]
        total = sum(len(c) for c in non_empty)
        assert total == 3

    def test_all_indices_present(self):
        stops = [(float(i), float(i)) for i in range(20)]
        clusters = _kmeans_cluster(stops, k=4)
        all_indices = sorted(idx for c in clusters for idx in c)
        assert all_indices == list(range(20))

    def test_deterministic(self):
        stops = [(float(i % 10), float(i // 10)) for i in range(50)]
        result1 = _kmeans_cluster(stops, k=5)
        result2 = _kmeans_cluster(stops, k=5)
        # Same input → same output (no random initialisation)
        groups1 = sorted([sorted(c) for c in result1])
        groups2 = sorted([sorted(c) for c in result2])
        assert groups1 == groups2


# --- _chain_clusters ---

class TestChainClusters:
    def test_starts_with_cluster_nearest_to_start(self):
        stops = [
            (0.0, 0.0),   # index 0 — near start
            (100.0, 0.0), # index 1 — far
        ]
        clusters = [[0], [1]]
        start = (-1.0, 0.0)  # just west of stop 0
        ordered = _chain_clusters(clusters, stops, start)
        assert ordered[0] == [0]
        assert ordered[1] == [1]

    def test_visits_all_clusters(self):
        stops = [(float(i * 10), 0.0) for i in range(5)]
        clusters = [[i] for i in range(5)]
        ordered = _chain_clusters(clusters, stops, (0.0, 0.0))
        assert len(ordered) == 5
        all_indices = [c[0] for c in ordered]
        assert sorted(all_indices) == list(range(5))

    def test_single_cluster_returned_as_is(self):
        stops = [(1.0, 2.0), (3.0, 4.0)]
        clusters = [[0, 1]]
        ordered = _chain_clusters(clusters, stops, (0.0, 0.0))
        assert ordered == [[0, 1]]


# --- geocode_address ---

@pytest.mark.asyncio
class TestGeocodeAddress:
    async def test_returns_lng_lat_on_success(self):
        response = {"features": [{"geometry": {"coordinates": [-112.074, 33.448]}}]}
        mock_session = _make_session(response)

        result = await geocode_address(mock_session, "123 Main St, Phoenix, AZ")

        assert result == (-112.074, 33.448)

    async def test_returns_none_when_no_features(self):
        mock_session = _make_session({"features": []})
        result = await geocode_address(mock_session, "Nonexistent Place")
        assert result is None

    async def test_returns_none_for_empty_address(self):
        mock_session = MagicMock()
        result = await geocode_address(mock_session, "   ")
        assert result is None
        mock_session.get.assert_not_called()

    async def test_returns_none_on_exception(self):
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("network error"))
        result = await geocode_address(mock_session, "123 Main St")
        assert result is None


# --- geocode_agents ---

@pytest.mark.asyncio
class TestGeocodeAgents:
    async def test_populates_lat_lng_on_agents(self):
        response = {"features": [{"geometry": {"coordinates": [-112.0, 33.4]}}]}
        mock_session = _make_session(response)

        agents = [{"address": "123 Main", "city": "Phoenix, AZ"}]
        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            await geocode_agents(agents)

        assert agents[0]["lng"] == -112.0
        assert agents[0]["lat"] == 33.4

    async def test_sets_empty_strings_when_geocoding_fails(self):
        mock_session = _make_session({"features": []})

        agents = [{"address": "Bad Address", "city": "Nowhere"}]
        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            await geocode_agents(agents)

        assert agents[0]["lng"] == ""
        assert agents[0]["lat"] == ""

    async def test_skips_geocoding_when_no_api_key(self):
        agents = [{"address": "123 Main", "city": "Phoenix"}]
        with patch("services.routing.settings") as mock_settings:
            mock_settings.openrouteservice_api_key = None
            await geocode_agents(agents)

        assert agents[0]["lng"] == ""
        assert agents[0]["lat"] == ""


# --- optimize_route ---

@pytest.mark.asyncio
class TestOptimizeRoute:
    async def test_returns_empty_for_no_stops(self):
        indices, duration = await optimize_route((0.0, 0.0), (0.0, 0.0), [])
        assert indices == []
        assert duration == 0

    async def test_returns_ordered_indices_from_ors(self):
        ors_response = {
            "routes": [{
                "steps": [
                    {"type": "start"},
                    {"type": "job", "id": 1},
                    {"type": "job", "id": 0},
                    {"type": "end"},
                ],
                "duration": 3600,
            }]
        }
        mock_session = _make_session(ors_response)

        stops = [(-112.0, 33.4), (-112.1, 33.5)]
        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            indices, duration = await optimize_route((0.0, 0.0), (0.0, 0.0), stops)

        assert indices == [1, 0]
        assert duration == 3600

    async def test_falls_back_to_sequential_order_when_ors_returns_no_routes(self):
        ors_response = {"routes": []}
        mock_session = _make_session(ors_response)

        stops = [(-112.0, 33.4), (-112.1, 33.5)]
        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            indices, duration = await optimize_route((0.0, 0.0), (0.0, 0.0), stops)

        assert indices == [0, 1]
        assert duration == 0

    async def test_raises_on_ors_error_response(self):
        ors_response = {"error": "Quota exceeded"}
        mock_session = _make_session(ors_response)

        stops = [(-112.0, 33.4)]
        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(RuntimeError, match="ORS optimization error"):
                await optimize_route((0.0, 0.0), (0.0, 0.0), stops)

    async def test_clustering_used_above_threshold(self):
        """With 160 stops, optimize_route should cluster before calling ORS."""
        ors_response = {
            "routes": [{"steps": [{"type": "job", "id": i} for i in range(40)], "duration": 100}]
        }
        mock_session = _make_session(ors_response)

        # 160 stops spread across 4 geographic regions
        stops = []
        for region_lng in [0.0, 10.0, 20.0, 30.0]:
            for i in range(40):
                stops.append((region_lng + i * 0.001, 33.0))

        with patch("services.routing.aiohttp.ClientSession", return_value=mock_session):
            with patch("services.routing._kmeans_cluster") as mock_cluster:
                # Return 4 clusters of 40 stops each
                mock_cluster.return_value = [list(range(i * 40, (i + 1) * 40)) for i in range(4)]
                with patch("services.routing._chain_clusters", side_effect=lambda c, s, start: c):
                    indices, duration = await optimize_route((0.0, 0.0), (0.0, 0.0), stops)

        mock_cluster.assert_called_once()
        assert len(indices) == 160
