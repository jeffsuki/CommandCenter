#!/usr/bin/env python3
"""
Notion -> Google Calendar sync.

Reads meetings from the Command Center Tasks database (tasks tagged "Meeting"
with a Date set) and creates/updates matching events in a dedicated Google
Calendar. One-way: create + update only (does not delete).

Idempotent: the Google event id is derived from the Notion page id, so
re-running updates the same event instead of duplicating it.
"""

import os
import datetime
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---- Config from environment (GitHub secrets) ----
NOTION_TOKEN         = os.environ["NOTION_TOKEN"]
NOTION_DB_ID         = os.environ["NOTION_TASKS_DB_ID"]
GOOGLE_CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REFRESH_TOKEN = os.environ["GOOGLE_REFRESH_TOKEN"]
GOOGLE_CALENDAR_ID   = os.environ["GOOGLE_CALENDAR_ID"]
TIMEZONE             = os.environ.get("TIMEZONE", "Asia/Jakarta")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def notion_query_meetings():
    """Return all Notion pages tagged 'Meeting' that have a Date.

    Includes Done/Archived ones too, so we can CANCEL their calendar events
    (Phase 1.5). We decide create-vs-cancel per page in main().
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Tags", "multi_select": {"contains": "Meeting"}},
                {"property": "Date", "date": {"is_not_empty": True}},
            ]
        }
    }
    results = []
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        results.extend(data["results"])
        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break
    return results


def is_removed(page):
    """True if the meeting should NOT be on the calendar (Done, Cancelled, or Archived)."""
    status = page["properties"].get("Status", {}).get("status")
    if status and status.get("name") in ("Done", "Cancelled"):
        return True
    if page["properties"].get("Archive", {}).get("checkbox"):
        return True
    return False


def cancel_event(service, page):
    event_id = "cc" + page["id"].replace("-", "")
    try:
        service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
        print(f"  removed: {title_of(page)}")
    except HttpError as e:
        if e.resp.status in (404, 410):
            pass  # already gone
        else:
            print(f"  ERROR removing ({e.resp.status}): {title_of(page)}")


def google_service():
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def title_of(page):
    parts = page["properties"].get("Name", {}).get("title", [])
    text = "".join(p.get("plain_text", "") for p in parts).strip()
    return text or "(untitled meeting)"


def select_of(page, prop):
    s = page["properties"].get(prop, {}).get("select")
    return s["name"] if s else None


def plus_one_day(date_str):
    d = datetime.date.fromisoformat(date_str)
    return (d + datetime.timedelta(days=1)).isoformat()


def plus_one_hour(dt_str):
    dt = datetime.datetime.fromisoformat(dt_str)
    return (dt + datetime.timedelta(hours=1)).isoformat()


def build_event(page):
    date = page["properties"]["Date"]["date"]
    start = date["start"]
    end = date.get("end")
    company = select_of(page, "Company")
    summary = title_of(page)
    description = (f"Company: {company}\n" if company else "") + \
                  "Created from Notion Command Center"

    if "T" in start:  # has a time -> timed event
        start_body = {"dateTime": start, "timeZone": TIMEZONE}
        end_body = {"dateTime": end or plus_one_hour(start), "timeZone": TIMEZONE}
    else:             # date only -> all-day event
        start_body = {"date": start}
        end_body = {"date": plus_one_day(end or start)}  # Google end.date is exclusive

    # Google event ids: base32hex (0-9, a-v). Notion hex ids qualify; prefix keeps it safe.
    event_id = "cc" + page["id"].replace("-", "")
    return {
        "id": event_id,
        "summary": summary,
        "description": description,
        "start": start_body,
        "end": end_body,
    }


def upsert(service, event):
    try:
        service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        print(f"  created: {event['summary']}")
    except HttpError as e:
        if e.resp.status == 409:  # already exists -> update
            service.events().update(
                calendarId=GOOGLE_CALENDAR_ID, eventId=event["id"], body=event
            ).execute()
            print(f"  updated: {event['summary']}")
        else:
            print(f"  ERROR ({e.resp.status}): {event['summary']} -> {e}")


def main():
    service = google_service()
    meetings = notion_query_meetings()
    print(f"Found {len(meetings)} meeting(s) tagged 'Meeting' with a date.")
    for page in meetings:
        if is_removed(page):
            cancel_event(service, page)      # Phase 1.5: Done/Archived -> remove
        else:
            upsert(service, build_event(page))
    print("Done.")


if __name__ == "__main__":
    main()
