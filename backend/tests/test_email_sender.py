from unittest.mock import MagicMock, patch

import pytest

from services.email_sender import _build_html, _format_duration, _maps_link, _maps_links


# --- _format_duration ---

class TestFormatDuration:
    def test_minutes_only(self):
        assert _format_duration(1800) == "30m"

    def test_hours_and_minutes(self):
        assert _format_duration(3660) == "1h 1m"

    def test_exactly_one_hour(self):
        assert _format_duration(3600) == "1h 0m"

    def test_zero(self):
        assert _format_duration(0) == "0m"

    def test_two_hours(self):
        assert _format_duration(7200) == "2h 0m"


# --- _maps_link (legacy, ≤8 stops) ---

class TestMapsLink:
    def _stop(self, address, city="Phoenix, AZ"):
        return {"address": address, "city": city}

    def test_returns_none_for_single_stop(self):
        assert _maps_link([self._stop("123 Main")]) is None

    def test_returns_none_for_more_than_8_stops(self):
        stops = [self._stop(f"{i} St") for i in range(9)]
        assert _maps_link(stops) is None

    def test_two_stops_no_waypoints(self):
        stops = [self._stop("123 Main St"), self._stop("456 Oak Ave")]
        url = _maps_link(stops)
        assert url is not None
        assert "maps/dir" in url
        assert "Main" in url
        assert "Oak" in url

    def test_three_stops_includes_waypoint(self):
        stops = [self._stop("A"), self._stop("B"), self._stop("C")]
        url = _maps_link(stops)
        assert url is not None
        assert "A" in url and "B" in url and "C" in url


# --- _maps_links (segmented, handles any length) ---

class TestMapsLinks:
    def _stop(self, address, city="Phoenix, AZ"):
        return {"address": address, "city": city}

    def test_returns_empty_for_single_stop(self):
        assert _maps_links([self._stop("123 Main")]) == []

    def test_returns_empty_for_no_stops(self):
        assert _maps_links([]) == []

    def test_returns_one_url_for_short_route(self):
        stops = [self._stop(f"{i} St") for i in range(5)]
        urls = _maps_links(stops)
        assert len(urls) == 1
        assert "maps/dir" in urls[0]

    def test_returns_one_url_at_segment_boundary(self):
        stops = [self._stop(f"{i} St") for i in range(9)]
        urls = _maps_links(stops)
        assert len(urls) == 1

    def test_segments_long_route(self):
        stops = [self._stop(f"{i} St") for i in range(20)]
        urls = _maps_links(stops)
        assert len(urls) > 1

    def test_all_stops_covered_across_segments(self):
        """Every stop address should appear in at least one segment URL."""
        stops = [self._stop(f"Stop{i}") for i in range(15)]
        urls = _maps_links(stops)
        combined = " ".join(urls)
        for i in range(15):
            assert f"Stop{i}" in combined

    def test_adjacent_segments_share_boundary_stop(self):
        """Last stop of segment N should appear in segment N+1 (continuity)."""
        stops = [self._stop(f"Stop{i}") for i in range(18)]
        urls = _maps_links(stops)
        assert len(urls) >= 2
        # Stop8 (index 8) is the last in segment 1 and first in segment 2
        assert "Stop8" in urls[0]
        assert "Stop8" in urls[1]


# --- _build_html ---

class TestBuildHtml:
    def _result(self, routes=None):
        return {
            "sheet_url": "https://docs.google.com/spreadsheets/d/abc",
            "city_count": 2,
            "agent_count": 5,
            "cities": ["Phoenix, AZ", "Tempe, AZ"],
            "city_counts": {"Phoenix, AZ": 3, "Tempe, AZ": 2},
            "routes": routes or {},
        }

    def test_contains_sheet_url(self):
        html = _build_html(self._result())
        assert "https://docs.google.com/spreadsheets/d/abc" in html

    def test_contains_city_names(self):
        html = _build_html(self._result())
        assert "Phoenix, AZ" in html
        assert "Tempe, AZ" in html

    def test_shows_no_routes_message_when_routes_empty(self):
        html = _build_html(self._result(routes={}))
        assert "Route optimization was not run" in html

    def test_shows_route_table_when_routes_present(self):
        routes = {
            "Phoenix, AZ": {
                "stop_count": 1,
                "total_duration_seconds": 600,
                "ordered_agents": [{"name": "Smith Agency", "address": "1 Main", "city": "Phoenix, AZ"}],
            }
        }
        html = _build_html(self._result(routes=routes))
        assert "Smith Agency" in html
        assert "1 Main" in html

    def test_all_cities_label_used_for_all_key(self):
        routes = {
            "all": {
                "stop_count": 2,
                "total_duration_seconds": 1200,
                "ordered_agents": [],
            }
        }
        html = _build_html(self._result(routes=routes))
        assert "All Cities Combined" in html

    def test_maps_link_present_in_route_section(self):
        routes = {
            "Phoenix, AZ": {
                "stop_count": 3,
                "total_duration_seconds": 900,
                "ordered_agents": [
                    {"name": f"Agent {i}", "address": f"{i} Main St", "city": "Phoenix, AZ"}
                    for i in range(3)
                ],
            }
        }
        html = _build_html(self._result(routes=routes))
        assert "maps/dir" in html

    def test_segmented_maps_links_for_long_route(self):
        routes = {
            "Phoenix, AZ": {
                "stop_count": 18,
                "total_duration_seconds": 3600,
                "ordered_agents": [
                    {"name": f"Agent {i}", "address": f"{i} Main St", "city": "Phoenix, AZ"}
                    for i in range(18)
                ],
            }
        }
        html = _build_html(self._result(routes=routes))
        # Multiple Maps links expected for an 18-stop route
        assert html.count("maps/dir") >= 2
