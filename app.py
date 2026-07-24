#!/usr/bin/env python3
"""USAGS dashboard (MVP). Renders tiles from various sources; first tile is the
Google Calendar 'upcoming events'. More tiles (Shopify sales, Zendesk) slot in
the same way: a provider module returns data, a render_* function makes a card.

NOTE: no login yet — bind to localhost for local testing. Before this goes on the
internet we add the same auth + Caddy/HTTPS as the agent (see README).
"""
import os, html as _html
from flask import Flask
from dotenv import load_dotenv

load_dotenv()          # load .env before providers read config
import gcal
import shopify
app = Flask(__name__)

def esc(s): return _html.escape(str(s or ""))

CUR_SYM = {"USD": "$", "CAD": "$", "AUD": "$", "NZD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
def cur_symbol(code):
    code = (code or "").upper()
    return CUR_SYM.get(code, (code + " ") if code else "")

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#eef2f5;color:#13242e;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}
.top{background:#0E2C3B;color:#fff;padding:16px 24px;font-weight:600;letter-spacing:.04em}
.grid{max-width:1100px;margin:0 auto;padding:24px 18px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
.tile{background:#fff;border:1px solid #d5dee4;border-radius:12px;overflow:hidden}
.tile h2{margin:0;padding:14px 18px;font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:#155C7A;border-bottom:1px solid #eef2f5}
.tile .body{padding:6px 18px 14px}
.evt{display:flex;gap:12px;align-items:flex-start;padding:11px 0;border-bottom:1px dashed #e1e8ec}
.evt:last-child{border-bottom:none}
.evt .when{flex:0 0 auto;width:120px;font-size:12.5px;color:#566772;padding-top:2px}
.evt .info{min-width:0;flex:1 1 auto}
.evt .what{font-size:15px;overflow-wrap:anywhere}
.evt .loc{font-size:12.5px;color:#8a97a0;overflow-wrap:anywhere}
.empty{color:#66727a;font-size:14px;padding:10px 0}
.err{color:#933;font-size:13.5px;padding:10px 0}
a{color:#155C7A;text-decoration:none}
.sales{display:flex;flex-direction:column;gap:8px}
.stat{display:flex;align-items:baseline;justify-content:space-between;gap:12px;border:1px solid #eef2f5;border-radius:10px;padding:11px 14px;background:#f7fafc}
.stat .lbl{flex:0 0 auto;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:#8a97a0}
.stat .vals{flex:1 1 auto;min-width:0;text-align:right}
.stat .rev{font-size:18px;font-weight:600;color:#0E2C3B}
.stat .ord{font-size:12px;color:#566772;margin-top:2px}
.cur{font-size:12px;font-weight:400;color:#8a97a0}
.note{font-size:12px;color:#8a97a0;padding-top:8px}
@media(max-width:520px){.sales{grid-template-columns:1fr}}
"""

def render_calendar():
    data = gcal.upcoming_events(8)
    if "error" in data:
        inner = f"<div class=err>{esc(data['error'])}</div>"
    elif not data["events"]:
        inner = "<div class=empty>No upcoming events.</div>"
    else:
        rows = []
        for e in data["events"]:
            loc = f"<div class=loc>{esc(e['location'])}</div>" if e["location"] else ""
            title = esc(e["title"])
            if e["url"]:
                title = f"<a href='{esc(e['url'])}' target='_blank' rel='noopener'>{title}</a>"
            rows.append(f"<div class=evt><div class=when>{esc(e['when'])}</div>"
                        f"<div class=info><div class=what>{title}</div>{loc}</div></div>")
        inner = "".join(rows)
    return f"<div class=tile><h2>Upcoming Calendar</h2><div class=body>{inner}</div></div>"

def render_sales():
    data = shopify.sales()
    title = "Shopify Sales"
    if "error" in data:
        inner = f"<div class=err>{esc(data['error'])}</div>"
    else:
        cur = data.get("currency", "")
        sym = cur_symbol(cur)
        cards = []
        for w in data["windows"]:
            rev = f"{sym}{w['revenue']:,.2f}"
            cards.append(f"<div class=stat><div class=lbl>{esc(w['label'])}</div>"
                         f"<div class=vals><div class=rev>{esc(rev)}</div>"
                         f"<div class=ord>{w['orders']} order{'s' if w['orders']!=1 else ''}</div></div></div>")
        note = "<div class=note>Showing the most recent 30 days (capped).</div>" if data.get("capped") else ""
        inner = f"<div class=sales>{''.join(cards)}</div>{note}"
        shop = esc(data.get("shop") or "")
        title = f"Shopify Sales · {shop} <span class=cur>({esc(cur)})</span>" if shop else f"Shopify Sales <span class=cur>({esc(cur)})</span>"
    return f"<div class=tile><h2>{title}</h2><div class=body>{inner}</div></div>"

@app.route("/")
def home():
    tiles = [render_calendar(), render_sales()]  # more tiles appended here later
    return ("<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>USAGS Dashboard</title>"
            f"<style>{CSS}</style>"
            "<div class=top>USAGS Dashboard</div>"
            f"<div class=grid>{''.join(tiles)}</div>")

if __name__ == "__main__":
    app.run(host=os.getenv("DASH_BIND", "127.0.0.1"), port=int(os.getenv("DASH_PORT", "8002")))
