import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW = ["Agent Name", "Address", "City", "Phone", "Website", "Rating", "Latitude", "Longitude", "Source"]


def _get_credentials():
    if not settings.google_service_account_json:
        raise RuntimeError("Google credentials not configured")
    try:
        info = json.loads(settings.google_service_account_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON: {e}") from e
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def get_sheets_service():
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)


def _agent_to_row(agent: dict) -> list:
    return [
        agent.get("name", ""),
        agent.get("address", ""),
        agent.get("city", ""),
        agent.get("phone", ""),
        agent.get("website", ""),
        agent.get("rating", ""),
        agent.get("lat", ""),
        agent.get("lng", ""),
        agent.get("source", ""),
    ]


def write_agents_to_sheet(spreadsheet_id: str, agents: list[dict], cities: list[str]):
    """Add a new set of tabs to an existing spreadsheet for this run."""
    sheets = get_sheets_service()
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    all_tab_name = f"All Cities — {date_str}"
    city_tab_names = [f"{city} — {date_str}" for city in cities]

    # Create all new tabs in one batch
    requests = [{"addSheet": {"properties": {"title": all_tab_name}}}]
    for tab_name in city_tab_names:
        requests.append({"addSheet": {"properties": {"title": tab_name}}})

    try:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests},
        ).execute()
    except HttpError as e:
        if e.resp.status == 403:
            raise RuntimeError(
                "Service account does not have Editor access to the spreadsheet. "
                "Share it with path-finder-service@path-finder-496703.iam.gserviceaccount.com"
            ) from e
        raise

    # Build per-city agent lists
    agents_by_city: dict[str, list[dict]] = {city: [] for city in cities}
    for agent in agents:
        city = agent.get("city", "")
        if city in agents_by_city:
            agents_by_city[city].append(agent)

    # Prepare batchUpdate value data
    data = []

    all_rows = sorted(agents, key=lambda a: a.get("name", "").lower())
    data.append({
        "range": f"'{all_tab_name}'!A1",
        "values": [HEADER_ROW] + [_agent_to_row(a) for a in all_rows],
    })

    for city, tab_name in zip(cities, city_tab_names):
        city_rows = sorted(agents_by_city[city], key=lambda a: a.get("name", "").lower())
        data.append({
            "range": f"'{tab_name}'!A1",
            "values": [HEADER_ROW] + [_agent_to_row(a) for a in city_rows],
        })

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()

    logger.info("Wrote %d agents to spreadsheet %s (%s)", len(agents), spreadsheet_id, date_str)


def build_sheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"


def create_and_populate_sheet(agents: list[dict], cities: list[str]) -> str:
    if settings.test_mode:
        spreadsheet_id = settings.test_google_spreadsheet_id
        if not spreadsheet_id:
            raise RuntimeError(
                "TEST_GOOGLE_SPREADSHEET_ID not configured — add it to your .env for test mode"
            )
    else:
        spreadsheet_id = settings.google_spreadsheet_id
        if not spreadsheet_id:
            raise RuntimeError(
                "GOOGLE_SPREADSHEET_ID not configured — create a Google Sheet, share it with the service account, "
                "and add the spreadsheet ID to your .env"
            )
    write_agents_to_sheet(spreadsheet_id, agents, cities)
    return build_sheet_url(spreadsheet_id)
