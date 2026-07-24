"""Unit-test the sales aggregation, ShopifyQL row parsing, and tile render. No network."""
import os, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shopify, app as A

today = date(2026, 7, 24)
days = [  # (date, total_sales, orders, returns, returned_items)
    (date(2026, 7, 24), 150.00, 2, 12.00, 1),  # today (incl. $12 / 1 item refund)
    (date(2026, 7, 20), 25.00, 1, 5.00, 2),    # within 7d
    (date(2026, 7, 5), 10.00, 1, 0.00, 0),     # within 30d only
    (date(2026, 6, 1), 999.00, 5, 40.00, 3),   # older than 30d
]

# 1) aggregation windows (7d = today + 6 prior; 30d = today + 29 prior)
w = {x["label"]: x for x in shopify._aggregate(days, today)}
assert w["Today"]["orders"] == 2 and w["Today"]["revenue"] == 150.00 and w["Today"]["refunds"] == 12.00 and w["Today"]["refund_items"] == 1, w["Today"]
assert w["Last 7 days"]["orders"] == 3 and w["Last 7 days"]["revenue"] == 175.00 and w["Last 7 days"]["refunds"] == 17.00 and w["Last 7 days"]["refund_items"] == 3, w["Last 7 days"]
assert w["Last 30 days"]["orders"] == 4 and w["Last 30 days"]["revenue"] == 185.00, w["Last 30 days"]
print("aggregate OK:", {k: (v["orders"], v["revenue"], v["refunds"], v["refund_items"]) for k, v in w.items()})

# 2) empty data -> all zeros, no crash
z = {x["label"]: x for x in shopify._aggregate([], today)}
assert z["Today"]["orders"] == 0 and z["Today"]["revenue"] == 0.0
print("empty OK")

# 3) ShopifyQL rows parse from BOTH dict-keyed and positional-list shapes;
#    'returns' comes back negative and is stored as a positive refund amount
cols = ["day", "total_sales", "orders", "returns", "quantity_returned"]
as_dicts = [{"day": "2026-07-24", "total_sales": "150.00", "orders": 2, "returns": "-12.00", "quantity_returned": "-1"}]
as_lists = [["2026-07-24", "150.00", 2, "-12.00", "-1"]]
assert shopify._parse_rows(cols, as_dicts) == [(date(2026, 7, 24), 150.0, 2, 12.0, 1)], shopify._parse_rows(cols, as_dicts)
assert shopify._parse_rows(cols, as_lists) == [(date(2026, 7, 24), 150.0, 2, 12.0, 1)], shopify._parse_rows(cols, as_lists)
# day-timestamp with time component still parses; missing 'returns'/'quantity_returned' -> 0
assert shopify._parse_rows(["day", "total_sales", "orders"],
                           [{"day": "2026-07-24T00:00:00", "total_sales": "5", "orders": "1"}]) \
    == [(date(2026, 7, 24), 5.0, 1, 0.0, 0)]
print("parse OK")

# 4) render_sales handles data + error
shopify.sales = lambda: {"shop": "USA Gundam Store", "currency": "USD",
                         "windows": [{"label": "Today", "orders": 2, "revenue": 150.0, "refunds": 12.0, "refund_items": 1},
                                     {"label": "Last 7 days", "orders": 3, "revenue": 175.0, "refunds": 17.0, "refund_items": 3},
                                     {"label": "Last 30 days", "orders": 4, "revenue": 185.0, "refunds": 57.0, "refund_items": 6}]}
html = A.render_sales()
assert "Shopify Sales" in html and "$150.00" in html and "(USD)" in html and "2 orders" in html and "USA Gundam Store" in html
assert "Refunds" in html and "$12.00" in html and "1 item refunded" in html, html
print("render OK")

shopify.sales = lambda: {"error": "Shopify not configured"}
assert "Shopify not configured" in A.render_sales()
print("error render OK")

# 5) full page shows both tiles
import gcal
gcal.upcoming_events = lambda limit=8: {"events": [], "count": 0}
shopify.sales = lambda: {"shop": "S", "currency": "USD",
                         "windows": [{"label": "Today", "orders": 0, "revenue": 0.0, "refunds": 0.0, "refund_items": 0}]}
r = A.app.test_client().get("/")
assert r.status_code == 200 and b"Upcoming Calendar" in r.data and b"Shopify Sales" in r.data
print("page OK: calendar + sales tiles both render")

print("\nSHOPIFY SALES TILE VERIFIED")
