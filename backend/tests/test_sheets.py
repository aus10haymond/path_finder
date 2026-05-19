import pytest

from services.sheets import _agent_to_row, build_sheet_url


# --- _agent_to_row ---

class TestAgentToRow:
    def test_full_agent(self):
        agent = {
            "name": "Smith Agency",
            "address": "123 Main St",
            "city": "Phoenix, AZ",
            "phone": "555-0001",
            "website": "https://smith.example.com",
            "rating": 4.5,
            "lat": 33.448,
            "lng": -112.074,
            "source": "serpapi",
        }
        row = _agent_to_row(agent)
        assert row == [
            "Smith Agency",
            "123 Main St",
            "Phoenix, AZ",
            "555-0001",
            "https://smith.example.com",
            4.5,
            33.448,
            -112.074,
            "serpapi",
        ]

    def test_missing_fields_default_to_empty_string(self):
        row = _agent_to_row({})
        assert row == ["", "", "", "", "", "", "", "", ""]

    def test_partial_agent(self):
        agent = {"name": "Jones Insurance", "city": "Tempe, AZ"}
        row = _agent_to_row(agent)
        assert row[0] == "Jones Insurance"
        assert row[2] == "Tempe, AZ"
        assert row[1] == ""


# --- build_sheet_url ---

class TestBuildSheetUrl:
    def test_returns_correct_url(self):
        url = build_sheet_url("abc123")
        assert url == "https://docs.google.com/spreadsheets/d/abc123"

    def test_different_ids(self):
        assert "xyz" in build_sheet_url("xyz")
