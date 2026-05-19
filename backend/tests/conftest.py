import os
import pytest

# Ensure no real API keys are used during tests
os.environ.setdefault("SERPAPI_KEY", "test-serpapi-key")
os.environ.setdefault("OPENROUTESERVICE_API_KEY", "test-ors-key")
os.environ.setdefault("SENDGRID_API_KEY", "test-sg-key")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")
os.environ.setdefault("RECIPIENT_EMAIL", "recipient@example.com")
os.environ.setdefault("SECRET_URL_TOKEN", "test-token")


@pytest.fixture
def sample_agents() -> list[dict]:
    return [
        {
            "name": "Smith Insurance Agency",
            "address": "123 Main St",
            "city": "Phoenix, AZ",
            "phone": "555-0001",
            "website": "https://smith.example.com",
            "rating": 4.5,
            "place_id": "place_001",
            "source": "serpapi",
            "lat": 33.4484,
            "lng": -112.0740,
        },
        {
            "name": "Jones Home & Life",
            "address": "456 Oak Ave",
            "city": "Phoenix, AZ",
            "phone": "555-0002",
            "website": "",
            "rating": 4.2,
            "place_id": "place_002",
            "source": "serpapi",
            "lat": 33.4500,
            "lng": -112.0700,
        },
    ]
