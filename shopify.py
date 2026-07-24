"""Shopify provider: sales summary tile (orders + revenue over time windows).

Read-only. Uses the same client-credentials token flow as the agent, then runs a
single ShopifyQL query (shopifyqlQuery, Admin API 2025-10+) that returns per-day
total_sales + orders for the last 30 days. Shopify aggregates server-side, so there
is no order-by-order pagination and no volume cap — one small response regardless of
how many orders the store does. Days are bucketed into Today / 7d / 30d in code,
anchored to the store's local calendar day. Requires the read_reports scope.

'total_sales' is Shopify's own sales metric (what Analytics shows), so the tile
matches the admin dashboard rather than re-summing raw order totals.
"""
import os, json, datetime, urllib.request, urllib.error, urllib.parse
from datetime import timezone, timedelta, date
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

API_VERSION = "2026-07"

# 31 daily rows (30d ago .. today). ShopifyQL day timestamps are in the shop's tz.
_SALES_QL = "FROM sales SHOW total_sales, orders, returns TIMESERIES day SINCE -30d UNTIL today ORDER BY day ASC"
_QL_Q = "query($q:String!){shopifyqlQuery(query:$q){tableData{columns{name} rows} parseErrors}}"
_SHOP_Q = "{ shop { name currencyCode ianaTimezone } }"

def _cfg():
    return (os.getenv("SHOPIFY_STORE_DOMAIN"), os.getenv("SHOPIFY_CLIENT_ID"), os.getenv("SHOPIFY_CLIENT_SECRET"))

def _post(domain, path, data, headers):
    req = urllib.request.Request(f"https://{domain}{path}", data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())

def _token(domain, cid, csec):
    form = urllib.parse.urlencode({"grant_type": "client_credentials",
                                   "client_id": cid, "client_secret": csec}).encode()
    return _post(domain, "/admin/oauth/access_token", form,
                 {"Content-Type": "application/x-www-form-urlencoded"})["access_token"]

def _gql(domain, tok, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    return _post(domain, f"/admin/api/{API_VERSION}/graphql.json", body,
                 {"Content-Type": "application/json", "X-Shopify-Access-Token": tok})

def _parse_rows(cols, rows):
    """ShopifyQL tableData -> [(date, total_sales, orders, returns)]. Rows may arrive
    as dicts keyed by column name or as positional lists; handle both. 'returns' is
    stored as a positive refund amount (ShopifyQL reports it negative)."""
    def val(row, name):
        if isinstance(row, dict): return row.get(name)
        try: return row[cols.index(name)]
        except (ValueError, IndexError): return None
    def num(row, name):
        try: return float(val(row, name) or 0)
        except (TypeError, ValueError): return 0.0
    out = []
    for r in rows:
        ds = str(val(r, "day") or "")[:10]
        try: d = date.fromisoformat(ds)
        except ValueError: continue
        out.append((d, num(r, "total_sales"), int(num(r, "orders")), abs(num(r, "returns"))))
    return out

def _aggregate(days, today):
    """days: [(date, total_sales, orders, returns)]; today: store-local date.
    Returns per-window totals. Pure/testable — no network."""
    windows = [("Today", today),
               ("Last 7 days", today - timedelta(days=6)),
               ("Last 30 days", today - timedelta(days=29))]
    out = []
    for label, start in windows:
        cnt = 0; rev = 0.0; ref = 0.0
        for d, ts, oc, rt in days:
            if d >= start:
                cnt += oc; rev += ts; ref += rt
        out.append({"label": label, "orders": cnt, "revenue": round(rev, 2), "refunds": round(ref, 2)})
    return out

def _today_local(tzname):
    tz = None
    if tzname and ZoneInfo:
        try: tz = ZoneInfo(tzname)
        except Exception: tz = None
    now = datetime.datetime.now(timezone.utc)
    return (now.astimezone(tz) if tz else now).date()

def sales():
    domain, cid, csec = _cfg()
    if not (domain and cid and csec):
        return {"error": "Shopify not configured (set SHOPIFY_STORE_DOMAIN / CLIENT_ID / CLIENT_SECRET)."}
    try:
        tok = _token(domain, cid, csec)
        shop = _gql(domain, tok, _SHOP_Q, {}).get("data", {}).get("shop", {}) or {}
        d = _gql(domain, tok, _QL_Q, {"q": _SALES_QL})
        if "errors" in d:
            return {"error": f"sales query failed: {json.dumps(d['errors'])[:300]}"}
        res = (d.get("data", {}) or {}).get("shopifyqlQuery") or {}
        if res.get("parseErrors"):
            return {"error": f"ShopifyQL error: {json.dumps(res['parseErrors'])[:300]}"}
        table = res.get("tableData") or {}
        cols = [c["name"] for c in table.get("columns", [])]
        days = _parse_rows(cols, table.get("rows", []))
        today = _today_local(shop.get("ianaTimezone"))
        return {"shop": shop.get("name", ""), "currency": shop.get("currencyCode", ""),
                "windows": _aggregate(days, today)}
    except Exception as e:
        return {"error": f"Shopify fetch failed: {e}"}
