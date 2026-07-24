"""Shopify provider: sales summary tile (orders + revenue over time windows).

Read-only. Uses the same client-credentials token flow as the agent. One paginated
pass over the last 30 days of orders is bucketed into Today / 7d / 30d in code, so
counts and revenue for all three windows come from a single fetch.
"""
import os, json, datetime, urllib.request, urllib.error, urllib.parse
from datetime import timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

API_VERSION = "2026-07"
_MAX_PAGES = 40           # 40 * 250 = up to 10k orders/30d before we flag "capped"

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

_SHOP_Q = "{ shop { name currencyCode ianaTimezone } }"
_ORDERS_Q = """query($q:String!,$after:String){orders(first:250,query:$q,sortKey:CREATED_AT,reverse:true,after:$after){
  edges{node{createdAt currentTotalPriceSet{shopMoney{amount}}}}
  pageInfo{hasNextPage endCursor}}}"""

def _window_starts(now_utc, tzname):
    """Start instants (UTC) for Today (store-local calendar day), 7d, 30d rolling."""
    tz = None
    if tzname and ZoneInfo:
        try: tz = ZoneInfo(tzname)
        except Exception: tz = None
    local = now_utc.astimezone(tz) if tz else now_utc
    midnight_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    today = midnight_local.astimezone(timezone.utc)
    return [("Today", today), ("Last 7 days", now_utc - timedelta(days=7)),
            ("Last 30 days", now_utc - timedelta(days=30))]

def _aggregate(orders, now_utc, tzname):
    """orders: list of {'created': iso, 'amount': float}. Returns per-window totals.
    Pure/testable — no network."""
    starts = _window_starts(now_utc, tzname)
    out = []
    for label, start in starts:
        cnt = 0; rev = 0.0
        for o in orders:
            try: dt = datetime.datetime.fromisoformat(o["created"])
            except Exception: continue
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            if dt >= start:
                cnt += 1; rev += float(o["amount"] or 0)
        out.append({"label": label, "orders": cnt, "revenue": round(rev, 2)})
    return out

def sales():
    domain, cid, csec = _cfg()
    if not (domain and cid and csec):
        return {"error": "Shopify not configured (set SHOPIFY_STORE_DOMAIN / CLIENT_ID / CLIENT_SECRET)."}
    try:
        tok = _token(domain, cid, csec)
        shop = _gql(domain, tok, _SHOP_Q, {}).get("data", {}).get("shop", {}) or {}
        now = datetime.datetime.now(timezone.utc)
        since = (now - timedelta(days=30)).strftime("created_at:>=%Y-%m-%dT%H:%M:%SZ")
        orders, after, capped = [], None, False
        for _ in range(_MAX_PAGES):
            d = _gql(domain, tok, _ORDERS_Q, {"q": since, "after": after})
            if "errors" in d:
                return {"error": f"orders query failed: {json.dumps(d['errors'])[:300]}"}
            conn = d["data"]["orders"]
            for e in conn["edges"]:
                n = e["node"]
                orders.append({"created": n["createdAt"],
                               "amount": n["currentTotalPriceSet"]["shopMoney"]["amount"]})
            if conn["pageInfo"]["hasNextPage"]:
                after = conn["pageInfo"]["endCursor"]
            else:
                break
        else:
            capped = True
        return {"shop": shop.get("name", ""), "currency": shop.get("currencyCode", ""),
                "windows": _aggregate(orders, now, shop.get("ianaTimezone")), "capped": capped}
    except Exception as e:
        return {"error": f"Shopify fetch failed: {e}"}
