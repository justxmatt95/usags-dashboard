# USAGS Dashboard

An internal dashboard that pulls the boss's key info into one page: Google
Calendar (built), then Shopify sales and Zendesk tickets (next).

Each source is a small provider module that returns data; a `render_*` function
turns it into a tile. Read-only.

## Setup (local, to get the calendar working)

```bash
cd usags-dashboard
python -m venv .venv
.venv\Scripts\activate            # Windows;  source .venv/bin/activate on Linux
pip install -r requirements.txt
cp .env.example .env              # then fill in GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
```

### One-time Google Calendar authorization
Run this on a machine **with a browser** (your laptop):
```bash
python authorize_gcal.py
```
A browser opens; sign in as the calendar's account and click **Allow**. It writes
`gcal_token.json` (contains the refresh token — gitignored, never commit it).

### Run the dashboard
```bash
python app.py
```
Open http://127.0.0.1:8002 — you should see the "Upcoming Calendar" tile.

## Deploying to the server (later)
Same pattern as the agent:
1. Copy `gcal_token.json` up to the server's dashboard dir (the refresh token lets
   the headless server refresh access tokens on its own).
2. Run under systemd, bound to `127.0.0.1`.
3. Front it with Caddy on its own subdomain (e.g. `dash.usags.ai`) for HTTPS.
4. Add a login (reuse the agent's per-user hashed-password + session hardening)
   **before** it faces the internet — right now there is no auth.

## Security notes
- Calendar access is **read-only**.
- Secrets (`.env`, `gcal_token.json`, `client_secret*.json`) are gitignored.
- No login yet — keep it on localhost until the auth step above is done.
