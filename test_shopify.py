"""Unit-test the sales aggregation + tile render with mock data. No network."""
import os, sys, datetime
from datetime import timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopify, app as A

now = datetime.datetime(2026, 7, 24, 18, 0, 0, tzinfo=timezone.utc)
orders = [
    {"created": "2026-07-24T14:00:00Z", "amount": "100.00"},  # today
    {"created": "2026-07-24T02:00:00Z", "amount": "50.00"},   # today (UTC) -- see tz note below
    {"created": "2026-07-20T10:00:00Z", "amount": "25.00"},   # within 7d
    {"created": "2026-07-05T10:00:00Z", "amount": "10.00"},   # within 30d only
    {"created": "2026-06-01T10:00:00Z", "amount": "999.00"},  # older than 30d (excluded by fetch, but test filter)
]

# 1) aggregation with UTC tz: Today = since UTC midnight 2026-07-24
w = {x["label"]: x for x in shopify._aggregate(orders, now, "UTC")}
assert w["Today"]["orders"] == 2 and w["Today"]["revenue"] == 150.00, w["Today"]
assert w["Last 7 days"]["orders"] == 3 and w["Last 7 days"]["revenue"] == 175.00, w["Last 7 days"]
assert w["Last 30 days"]["orders"] == 4 and w["Last 30 days"]["revenue"] == 185.00, w["Last 30 days"]
print("aggregate OK:", {k: (v["orders"], v["revenue"]) for k, v in w.items()})

# 2) timezone shifts the 'today' boundary (America/New_York = UTC-4 in July)
wny = {x["label"]: x for x in shopify._aggregate(orders, now, "America/New_York")}
# local midnight 07-24 NY = 04:00 UTC, so the 02:00Z order falls to "yesterday"
assert wny["Today"]["orders"] == 1 and wny["Today"]["revenue"] == 100.00, wny["Today"]
print("timezone OK: NY 'today' =", (wny["Today"]["orders"], wny["Today"]["revenue"]))

# 3) render_sales handles data + error
shopify.sales = lambda: {"shop": "USA Gundam Store", "currency": "USD",
                         "windows": [{"label": "Today", "orders": 2, "revenue": 150.0},
                                     {"label": "Last 7 days", "orders": 3, "revenue": 175.0},
                                     {"label": "Last 30 days", "orders": 4, "revenue": 185.0}],
                         "capped": False}
html = A.render_sales()
assert "Shopify Sales" in html and "USD 150.00" in html and "2 orders" in html and "USA Gundam Store" in html
print("render OK")

shopify.sales = lambda: {"error": "Shopify not configured"}
assert "Shopify not configured" in A.render_sales()
print("error render OK")

# 4) full page shows both tiles
import gcal
gcal.upcoming_events = lambda limit=8: {"events": [], "count": 0}
shopify.sales = lambda: {"shop": "S", "currency": "USD", "windows":
    [{"label": "Today", "orders": 0, "revenue": 0.0}], "capped": False}
r = A.app.test_client().get("/")
assert r.status_code == 200 and b"Upcoming Calendar" in r.data and b"Shopify Sales" in r.data
print("page OK: calendar + sales tiles both render")

print("\nSHOPIFY SALES TILE VERIFIED")
