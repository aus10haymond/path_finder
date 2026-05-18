import logging
from datetime import datetime
from urllib.parse import quote

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from config import settings

logger = logging.getLogger(__name__)


def _maps_link(stops: list[dict]) -> str | None:
    """Build a Google Maps directions URL for up to 8 stops."""
    if len(stops) > 8:
        return None
    addresses = [quote(f"{a.get('address', '')}, {a.get('city', '')}".strip(", ")) for a in stops]
    if len(addresses) < 2:
        return None
    origin = addresses[0]
    destination = addresses[-1]
    waypoints = "/".join(addresses[1:-1])
    url = f"https://www.google.com/maps/dir/{origin}"
    if waypoints:
        url += f"/{waypoints}"
    url += f"/{destination}"
    return url


def _format_duration(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _build_route_section(key: str, route: dict) -> str:
    label = "All Cities Combined" if key == "all" else key
    stops = route.get("ordered_agents", [])
    duration = _format_duration(route.get("total_duration_seconds", 0))
    maps_url = _maps_link(stops)

    rows = ""
    for i, stop in enumerate(stops, 1):
        rows += f"""
        <tr>
          <td style="padding:6px 8px;border-bottom:1px solid #eee;">{i}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #eee;">{stop.get('name','')}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #eee;">{stop.get('address','')}</td>
        </tr>"""

    maps_btn = ""
    if maps_url:
        maps_btn = f'<p><a href="{maps_url}" style="color:#1a73e8;">Open in Google Maps ({len(stops)} stops)</a></p>'

    return f"""
    <h3 style="margin:24px 0 8px;">{label}</h3>
    <p style="margin:0 0 8px;color:#555;">{route['stop_count']} stops &nbsp;·&nbsp; Est. drive time: {duration}</p>
    {maps_btn}
    <table style="border-collapse:collapse;width:100%;font-size:14px;">
      <thead>
        <tr style="background:#f5f5f5;">
          <th style="padding:6px 8px;text-align:left;">#</th>
          <th style="padding:6px 8px;text-align:left;">Agent</th>
          <th style="padding:6px 8px;text-align:left;">Address</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>"""


def _build_html(result: dict) -> str:
    sheet_url = result.get("sheet_url", "")
    city_count = result.get("city_count", 0)
    agent_count = result.get("agent_count", 0)
    cities = result.get("cities", [])
    city_counts = result.get("city_counts", {})
    routes = result.get("routes", {})
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    city_rows = "".join(
        f'<tr><td style="padding:5px 8px;border-bottom:1px solid #eee;">{c}</td>'
        f'<td style="padding:5px 8px;border-bottom:1px solid #eee;">{city_counts.get(c, 0)}</td></tr>'
        for c in cities
    )

    route_sections = "".join(_build_route_section(k, v) for k, v in routes.items()) if routes else (
        "<p style='color:#888;'>Route optimization was not run or did not return results.</p>"
    )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#222;">
  <h2 style="margin:0 0 4px;">Your Insurance Agent List is Ready</h2>
  <p style="color:#555;margin:0 0 24px;">{city_count} cities &nbsp;·&nbsp; {agent_count} agents found</p>

  <a href="{sheet_url}"
     style="display:inline-block;background:#1a73e8;color:#fff;padding:12px 24px;
            border-radius:6px;text-decoration:none;font-size:16px;font-weight:600;margin-bottom:32px;">
    Open Google Sheet
  </a>

  <h3 style="margin:0 0 8px;">Agents by City</h3>
  <table style="border-collapse:collapse;width:100%;font-size:14px;margin-bottom:32px;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:5px 8px;text-align:left;">City</th>
        <th style="padding:5px 8px;text-align:left;">Agents Found</th>
      </tr>
    </thead>
    <tbody>{city_rows}</tbody>
  </table>

  <h2 style="margin:0 0 16px;">Optimized Route</h2>
  {route_sections}

  <p style="margin:40px 0 0;color:#aaa;font-size:12px;">Generated {timestamp}</p>
</body>
</html>"""


async def send_results_email(result: dict) -> None:
    if not settings.sendgrid_api_key:
        logger.warning("SendGrid not configured — skipping email")
        return

    if settings.test_mode:
        recipient = settings.test_recipient_email
        if not recipient:
            logger.warning("TEST_RECIPIENT_EMAIL not configured — skipping email in test mode")
            return
    else:
        recipient = settings.recipient_email
        if not recipient:
            logger.warning("RECIPIENT_EMAIL not configured — skipping email")
            return

    city_count = result.get("city_count", 0)
    agent_count = result.get("agent_count", 0)
    subject = f"Your Insurance Agent List is Ready — {city_count} Cities, {agent_count} Agents"
    if settings.test_mode:
        subject = f"[TEST] {subject}"

    message = Mail(
        from_email=settings.sendgrid_from_email,
        to_emails=recipient,
        subject=subject,
        html_content=_build_html(result),
    )

    try:
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        logger.info("Email sent — status %s", response.status_code)
    except Exception as e:
        logger.error("SendGrid error: %s", e)
        raise
