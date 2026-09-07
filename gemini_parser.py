#!/usr/bin/env python3
"""
gemini_parser.py — turn a free-text Telegram message into structured item(s).

Uses the Gemini free tier (Flash model). Returns a list of dicts, each:
  {
    "type": "meeting" | "task",
    "name": str,
    "date": "YYYY-MM-DD",
    "start_time": "HH:MM" | None,   # meetings usually have this
    "end_time":   "HH:MM" | None,
    "company": one of the known companies | None,
    "priority": "Urgent"|"High"|"Medium"|"Low" | None,   # tasks
    "project_hint": str | None,     # raw text to fuzzy-match later
  }
"""

import os
import json
import datetime
import requests
from zoneinfo import ZoneInfo

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Jakarta")

COMPANIES = ["Above & Beyond", "Felindo", "Stock Market", "Personal", "Church"]

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def _today_str():
    return datetime.datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d (%A)")


def build_prompt(message):
    return f"""You convert a person's chat message into structured calendar/task items.

Today is {_today_str()} in timezone {TIMEZONE}.
Known companies (map loosely; "therapy center"/"ABA" -> "Above & Beyond";
"trucking"/"logistics" -> "Felindo"; "stocks"/"market" -> "Stock Market";
"church"/"ministry" -> "Church"; anything personal -> "Personal"): {COMPANIES}

Rules:
- A message may contain MULTIPLE items. Return every item.
- "meeting" = has a specific time and/or another person. "task" = a to-do.
- Resolve relative dates ("tomorrow", "next friday") to absolute YYYY-MM-DD.
- Times in 24h HH:MM. If a meeting has a start but no end, leave end_time null.
- priority only for tasks: Urgent/High/Medium/Low (null if unstated).
- project_hint: any project the user names, else null.
- company: best match from the list, else null.

Return ONLY valid JSON, no markdown, an array of objects with keys:
type, name, date, start_time, end_time, company, priority, project_hint.

Message: {json.dumps(message)}"""


def parse_message(message):
    body = {
        "contents": [{"parts": [{"text": build_prompt(message)}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    r = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    # responseMimeType=json should give clean JSON; guard anyway
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    items = json.loads(text)
    if isinstance(items, dict):
        items = [items]
    return items


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "meeting with christy jul 10 10-12 at the therapy center"
    print(json.dumps(parse_message(msg), indent=2))
