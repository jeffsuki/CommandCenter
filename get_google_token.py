#!/usr/bin/env python3
"""
Run this ONCE on your own computer to get a Google refresh token.

Prerequisites:
  1. In Google Cloud Console, create an OAuth client of type "Desktop app".
  2. Download its JSON and save it next to this script as: client_secret.json
  3. pip install google-auth-oauthlib
  4. python get_google_token.py

A browser window opens; sign in and allow Calendar access. The script then
prints your REFRESH TOKEN. Copy it into your GitHub secret GOOGLE_REFRESH_TOKEN.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("\n=================== COPY THESE ===================")
    print("GOOGLE_CLIENT_ID     =", creds.client_id)
    print("GOOGLE_CLIENT_SECRET =", creds.client_secret)
    print("GOOGLE_REFRESH_TOKEN =", creds.refresh_token)
    print("=================================================\n")
    if not creds.refresh_token:
        print("No refresh token returned. Revoke prior access at "
              "https://myaccount.google.com/permissions and run again.")

if __name__ == "__main__":
    main()
