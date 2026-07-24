#!/usr/bin/env python3
"""One-time Google Calendar authorization.

Run this ONCE on a machine with a browser (e.g. your laptop). It opens a browser,
you click "Allow" for the calendar you want to show, and it saves a refresh token
to gcal_token.json. Copy that file to the server's dashboard directory; the app
then refreshes access tokens on its own forever after.

    python authorize_gcal.py
"""
import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]  # read-only
HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(HERE, "gcal_token.json")

CID = os.getenv("GOOGLE_CLIENT_ID")
CSEC = os.getenv("GOOGLE_CLIENT_SECRET")
if not CID or not CSEC:
    raise SystemExit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env first.")

client_config = {
    "installed": {
        "client_id": CID,
        "client_secret": CSEC,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)   # opens your browser; consent once
with open(TOKEN_PATH, "w", encoding="utf-8") as f:
    f.write(creds.to_json())
print(f"\nSaved {TOKEN_PATH}")
print("Copy this file into the dashboard directory on the server (it holds the refresh token).")
