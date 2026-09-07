#!/usr/bin/env python3
"""
telegram_bot.py — Phase 2 inbound bot (polling model).

Each run:
  1. Fetches new Telegram updates (messages + button taps) since last offset.
  2. For text messages: parses them via Gemini into items, stores them in a
     pending queue, and sends a numbered confirmation with inline buttons.
  3. For button taps: adds the confirmed item(s) to Notion (meetings get the
     Meeting tag), or cancels.

State (offset + pending queue) is kept in state.json, committed back to the repo
by the GitHub Actions workflow so it persists between runs.
"""

import os
import json
import datetime
import difflib
import requests
from zoneinfo import ZoneInfo

from gemini_parser import parse_message, COMPANIES

NOTION_TOKEN       = os.environ["NOTION_TOKEN"]
NOTION_DB_ID       = os.environ["NOTION_TASKS_DB_ID"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = str(os.environ["TELEGRAM_CHAT_ID"])
TIMEZONE           = os.environ.get("TIMEZONE", "Asia/Jakarta")

STATE_FILE = "state.json"
TG = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


# ---------------- state ----------------
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"offset": 0, "pending": []}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------- telegram ----------------
def get_updates(offset):
    r = requests.get(f"{TG}/getUpdates",
                     params={"offset": offset, "timeout": 0}, timeout=30)
    r.raise_for_status()
    return r.json()["result"]


def send(text, buttons=None):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    requests.post(f"{TG}/sendMessage", json=payload, timeout=30).raise_for_status()


def answer_callback(cb_id, text=""):
    requests.post(f"{TG}/answerCallbackQuery",
                  json={"callback_query_id": cb_id, "text": text}, timeout=30)


# ---------------- notion ----------------
def notion_projects():
    """Return {lower_name: page_id} for fuzzy project matching."""
    # Projects DB id (from the Projects database, not Tasks)
    proj_db = os.environ.get("NOTION_PROJECTS_DB_ID", "")
    if not proj_db:
        return {}
    url = f"https://api.notion.com/v1/databases/{proj_db}/query"
    out = {}
    payload = {}
    while True:
        r = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        for p in data["results"]:
            t = p["properties"].get("Name", {}).get("title", [])
            name = "".join(x.get("plain_text", "") for x in t).strip()
            if name:
                out[name.lower()] = (name, p["id"])
        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break
    return out


def match_project(hint, projects):
    if not hint or not projects:
        return None
    names = list(projects.keys())
    best = difflib.get_close_matches(hint.lower(), names, n=1, cutoff=0.5)
    return projects[best[0]] if best else None


def create_notion_item(item, projects):
    props = {
        "Name": {"title": [{"text": {"content": item.get("name", "(untitled)")}}]},
    }
    # Date (with optional time range)
    date = item.get("date")
    if date:
        start = date
        end = None
        if item.get("type") == "meeting" and item.get("start_time"):
            start = f"{date}T{item['start_time']}:00"
            if item.get("end_time"):
                end = f"{date}T{item['end_time']}:00"
        dprop = {"start": start}
        if end:
            dprop["end"] = end
        props["Date"] = {"date": dprop}
    # Company
    if item.get("company") in COMPANIES:
        props["Company"] = {"select": {"name": item["company"]}}
    # Tags: meeting
    if item.get("type") == "meeting":
        props["Tags"] = {"multi_select": [{"name": "Meeting"}]}
    # Priority (tasks)
    if item.get("priority") in ("Urgent", "High", "Medium", "Low"):
        props["Priority"] = {"select": {"name": item["priority"]}}
    # Status default
    props["Status"] = {"status": {"name": "Not started"}}
    # Project relation (fuzzy)
    m = match_project(item.get("project_hint"), projects)
    if m:
        props["Project"] = {"relation": [{"id": m[1]}]}

    r = requests.post("https://api.notion.com/v1/pages",
                      headers=NOTION_HEADERS,
                      json={"parent": {"database_id": NOTION_DB_ID}, "properties": props},
                      timeout=30)
    r.raise_for_status()


# ---------------- formatting ----------------
def fmt_item(i, item):
    icon = "📅" if item.get("type") == "meeting" else "✅"
    bits = [item.get("name", "(untitled)")]
    if item.get("date"):
        d = item["date"]
        if item.get("start_time"):
            d += f" {item['start_time']}" + (f"–{item['end_time']}" if item.get("end_time") else "")
        bits.append(d)
    if item.get("company"):
        bits.append(item["company"])
    if item.get("priority"):
        bits.append(item["priority"])
    if item.get("project_hint"):
        bits.append(f"proj: {item['project_hint']}")
    return f"<b>{i}.</b> {icon} " + " · ".join(bits)


def confirm_buttons(n):
    rows = [[{"text": "✅ Add all", "callback_data": "add:all"},
             {"text": "❌ Cancel", "callback_data": "cancel"}]]
    # per-item toggle row(s), up to 4 per row
    item_btns = [{"text": f"Add {i}", "callback_data": f"add:{i}"} for i in range(1, n + 1)]
    for j in range(0, len(item_btns), 4):
        rows.append(item_btns[j:j + 4])
    return rows


# ---------------- main ----------------
def main():
    state = load_state()
    updates = get_updates(state["offset"])
    projects = None  # lazy-load only when needed

    for u in updates:
        state["offset"] = u["update_id"] + 1

        # ----- button taps -----
        if "callback_query" in u:
            cb = u["callback_query"]
            if str(cb["message"]["chat"]["id"]) != TELEGRAM_CHAT_ID:
                continue
            data = cb.get("data", "")
            answer_callback(cb["id"])
            pending = state.get("pending", [])
            if data == "cancel":
                state["pending"] = []
                send("❌ Cancelled. Nothing added.")
            elif data == "add:all":
                if projects is None:
                    projects = notion_projects()
                for item in pending:
                    create_notion_item(item, projects)
                send(f"✅ Added {len(pending)} item(s) to Command Center.")
                state["pending"] = []
            elif data.startswith("add:"):
                try:
                    idx = int(data.split(":")[1]) - 1
                except ValueError:
                    idx = -1
                if 0 <= idx < len(pending):
                    if projects is None:
                        projects = notion_projects()
                    create_notion_item(pending[idx], projects)
                    send(f"✅ Added: {pending[idx].get('name')}")
            save_state(state)
            continue

        # ----- text messages -----
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != TELEGRAM_CHAT_ID:
            continue
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        if text.lower() in ("/start", "/help"):
            send("Just text me a meeting or task naturally, e.g.\n"
                 "• <i>meeting with Ms Christy Jul 10 10-12 at the therapy center</i>\n"
                 "• <i>review payroll friday, high priority, felindo, warehouse ops project</i>\n"
                 "I'll show what I understood with buttons to confirm.")
            save_state(state)
            continue

        try:
            items = parse_message(text)
        except Exception as e:
            send(f"⚠️ Couldn't parse that ({e}). Try rephrasing.")
            save_state(state)
            continue

        if not items:
            send("⚠️ I didn't find a meeting or task in that message.")
            save_state(state)
            continue

        state["pending"] = items
        lines = ["I understood these — confirm below:", ""]
        lines += [fmt_item(i + 1, it) for i, it in enumerate(items)]
        send("\n".join(lines), buttons=confirm_buttons(len(items)))
        save_state(state)

    save_state(state)


if __name__ == "__main__":
    main()
