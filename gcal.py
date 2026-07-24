"""Google Calendar provider: read-only 'upcoming events' for the dashboard.

Uses the refresh token saved by authorize_gcal.py (gcal_token.json). Access tokens
are refreshed automatically; nothing here can modify the calendar (read-only scope).
"""
import os, datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(HERE, "gcal_token.json")

def _fmt(start_raw, all_day):
    """Human-readable 'when' string; cross-platform (no %-d)."""
    try:
        if all_day:
            d = datetime.date.fromisoformat(start_raw)
            return d.strftime("%a %b %d")
        dt = datetime.datetime.fromisoformat(start_raw)  # handles the trailing offset / 'Z' on 3.11+
        return dt.strftime("%a %b %d, %I:%M %p").replace(" 0", " ")
    except Exception:
        return start_raw

def _normalize(items):
    """Pure transform of Google event dicts -> tile-ready rows (unit-testable)."""
    out = []
    for e in items:
        start = e.get("start", {})
        raw = start.get("dateTime") or start.get("date") or ""
        all_day = "date" in start and "dateTime" not in start
        out.append({
            "title": e.get("summary", "(no title)"),
            "when": _fmt(raw, all_day),
            "start": raw,
            "all_day": all_day,
            "location": e.get("location", ""),
            "url": e.get("htmlLink", ""),
            "meet": e.get("hangoutLink", ""),
        })
    return out

def _creds():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds

def upcoming_events(limit=8):
    """Next `limit` events from now, soonest first. Returns {events, count} or {error}."""
    if not os.path.exists(TOKEN_PATH):
        return {"error": "Google Calendar not authorized yet — run authorize_gcal.py."}
    calendar_id = os.getenv("GCAL_CALENDAR_ID", "primary")
    try:
        svc = build("calendar", "v3", credentials=_creds(), cache_discovery=False)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        res = svc.events().list(calendarId=calendar_id, timeMin=now, maxResults=int(limit),
                                singleEvents=True, orderBy="startTime").execute()
        return {"events": _normalize(res.get("items", [])), "count": len(res.get("items", []))}
    except Exception as e:
        return {"error": f"calendar fetch failed: {e}"}
