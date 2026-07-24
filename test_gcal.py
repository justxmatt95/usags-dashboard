"""Unit-test the calendar normalization + the app tile render with mock data.
Does not hit Google (no token needed)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcal, app as A

# 1) _normalize: timed event, all-day event, missing title
items = [
    {"summary": "Vendor call", "start": {"dateTime": "2026-07-25T15:30:00-04:00"},
     "location": "Zoom", "htmlLink": "https://cal/e1"},
    {"start": {"date": "2026-07-26"}, "htmlLink": "https://cal/e2"},   # all-day, no title
]
rows = gcal._normalize(items)
assert rows[0]["title"] == "Vendor call" and not rows[0]["all_day"] and rows[0]["location"] == "Zoom"
assert rows[1]["title"] == "(no title)" and rows[1]["all_day"] is True
assert "Jul 25" in rows[0]["when"] and ":" in rows[0]["when"], rows[0]["when"]
assert "Jul 26" in rows[1]["when"] and ":" not in rows[1]["when"], rows[1]["when"]  # all-day = no time
print("normalize OK:", [r["when"] for r in rows])

# 2) render_calendar handles events, empty, and error without crashing
gcal.upcoming_events = lambda limit=8: {"events": rows, "count": len(rows)}
html = A.render_calendar()
assert "Upcoming Calendar" in html and "Vendor call" in html and "Zoom" in html
assert "&lt;" not in "Vendor call"  # sanity
print("render (events) OK")

gcal.upcoming_events = lambda limit=8: {"events": [], "count": 0}
assert "No upcoming events" in A.render_calendar()
gcal.upcoming_events = lambda limit=8: {"error": "not authorized yet"}
assert "not authorized yet" in A.render_calendar()
print("render (empty/error) OK")

# 3) full page renders via the Flask test client
c = A.app.test_client()
gcal.upcoming_events = lambda limit=8: {"events": rows, "count": len(rows)}
r = c.get("/")
assert r.status_code == 200 and b"USAGS Dashboard" in r.data and b"Vendor call" in r.data
print("page OK: dashboard renders the calendar tile")

# 4) HTML in an event title is escaped (no injection)
gcal.upcoming_events = lambda limit=8: {"events": gcal._normalize(
    [{"summary": "<script>x</script>", "start": {"date": "2026-07-27"}}]), "count": 1}
assert "<script>x</script>" not in A.render_calendar() and "&lt;script&gt;" in A.render_calendar()
print("escaping OK: event titles are HTML-escaped")

print("\nGCAL DASHBOARD VERIFIED")
