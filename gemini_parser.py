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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")  # optional override
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Jakarta")

COMPANIES = ["Above & Beyond", "Felindo", "Stock Market", "Personal", "Church"]

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

# Candidate models to try, in preference order (free-tier friendly first).
# If GEMINI_MODEL env is set, it's tried first.
CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
]


def list_available_models():
    """Return model names on this key that support generateContent."""
    r = requests.get(f"{API_ROOT}/models",
                     headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=30)
    r.raise_for_status()
    out = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            out.append(m["name"].replace("models/", ""))
    return out


def pick_model():
    """Choose a usable model: env override, else first candidate the key supports."""
    available = set(list_available_models())
    order = ([GEMINI_MODEL] if GEMINI_MODEL else []) + CANDIDATE_MODELS
    for name in order:
        if name and name in available:
            return name
    # last resort: any available flash model, else any available model
    flash = [m for m in available if "flash" in m]
    if flash:
        return sorted(flash)[0]
    if available:
        return sorted(available)[0]
    raise RuntimeError("No Gemini models available for this API key.")


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
    """Try models in order; if one 404s or errors, fall back to the next."""
    available = list_available_models()
    order = ([GEMINI_MODEL] if GEMINI_MODEL else []) + CANDIDATE_MODELS
    # keep only models the key actually lists, preserve order, then append any
    # other available flash models as further fallbacks
    tried = []
    candidates = [m for m in order if m in available]
    candidates += [m for m in available if "flash" in m and m not in candidates]
    if not candidates:
        candidates = available  # last resort: anything

    body_text = build_prompt(message)
    last_err = None
    for model in candidates:
        tried.append(model)
        url = f"{API_ROOT}/models/{model}:generateContent"
        body = {
            "contents": [{"parts": [{"text": body_text}]}],
            "generationConfig": {"temperature": 0,
                                 "responseMimeType": "application/json"},
        }
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": GEMINI_API_KEY,
                         "Content-Type": "application/json"},
                json=body,
                timeout=45,
            )
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
            items = json.loads(text)
            if isinstance(items, dict):
                items = [items]
            return items
        except Exception as e:
            last_err = e
            continue  # try next model
    raise RuntimeError(f"All models failed (tried {tried}). Last error: {last_err}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print("Models supporting generateContent on your key:")
        for m in list_available_models():
            print("  ", m)
        print("\nChosen:", pick_model())
    else:
        msg = " ".join(sys.argv[1:]) or "meeting with christy jul 10 10-12 at the therapy center"
        print(json.dumps(parse_message(msg), indent=2))
