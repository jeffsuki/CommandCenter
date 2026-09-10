#!/usr/bin/env python3
"""
Telegram twice-daily reminder.

Reads open tasks (Status != Done, not Archived) that are due today or overdue
from the Command Center Tasks database, groups them by Company, and sends a
digest to Telegram. Meant to run on a schedule (morning + after lunch).
"""

import os
import datetime
import requests
from zoneinfo import ZoneInfo

NOTION_TOKEN       = os.environ["NOTION_TOKEN"]
NOTION_DB_ID       = os.environ["NOTION_TASKS_DB_ID"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
TIMEZONE           = os.environ.get("TIMEZONE", "Asia/Jakarta")

TZ = ZoneInfo(TIMEZONE)

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

PRIORITY_EMOJI = {"Urgent": "🔴", "High": "🟠", "Medium": "🔵", "Low": "⚪"}


def query_due_tasks():
    """Fetch open, non-cancelled, non-archived items dated today or earlier
    (for overdue tasks) PLUS today's meetings. We fetch up to end of today and
    filter passed meetings out in build_message()."""
    today = datetime.datetime.now(TZ).date().isoformat()
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Status", "status": {"does_not_equal": "Done"}},
                {"property": "Status", "status": {"does_not_equal": "Cancelled"}},
                {"property": "Archive", "checkbox": {"equals": False}},
                {"property": "Date", "date": {"on_or_before": today}},
            ]
        },
        "sorts": [{"property": "Date", "direction": "ascending"}],
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


def meeting_passed(page):
    """True if this meeting is fully over (its END time is in the past), so skip
    it. Uses end time when available; falls back to start time; for date-only
    meetings, passed only once the day is over."""
    d = page["properties"].get("Date", {}).get("date")
    if not d:
        return False
    start = d.get("start")
    end = d.get("end")
    if not start:
        return False
    now = datetime.datetime.now(TZ)
    reference = end or start  # prefer end time; fall back to start
    if "T" in reference:  # has a time
        try:
            dt = datetime.datetime.fromisoformat(reference)
            return dt < now
        except ValueError:
            return False
    else:  # date-only: passed only after that day is over
        return reference < now.date().isoformat()


def title_of(page):
    parts = page["properties"].get("Name", {}).get("title", [])
    return "".join(p.get("plain_text", "") for p in parts).strip() or "(untitled)"


def select_of(page, prop):
    s = page["properties"].get(prop, {}).get("select")
    return s["name"] if s else None


def date_of(page):
    d = page["properties"].get("Date", {}).get("date")
    return d["start"][:10] if d and d.get("start") else None


def has_meeting_tag(page):
    tags = page["properties"].get("Tags", {}).get("multi_select", [])
    return any(t.get("name") == "Meeting" for t in tags)


def time_of(page):
    """Return 'HH:MM' if the Date has a time component, else None."""
    d = page["properties"].get("Date", {}).get("date")
    start = d.get("start") if d else None
    if start and "T" in start:
        # start looks like 2026-07-10T10:00:00+07:00
        return start[11:16]
    return None


def build_message(tasks):
    now = datetime.datetime.now(TZ)
    hour = now.hour
    greeting = "☀️ Morning brief" if hour < 11 else "🕐 Afternoon check-in"
    header = f"{greeting} — {now.strftime('%a %d %b %Y')}"

    if not tasks:
        return f"{header}\n\n✅ Nothing due today. All clear!"

    today = now.date().isoformat()

    # split meetings vs regular tasks
    meetings = [t for t in tasks if has_meeting_tag(t) and not meeting_passed(t)]
    todos = [t for t in tasks if not has_meeting_tag(t)]

    lines = [header, ""]

    # --- Meetings section: "Time - Title", sorted by time ---
    if meetings:
        # sort: timed meetings first (by time), then any without a time
        meetings.sort(key=lambda m: (time_of(m) is None, time_of(m) or ""))
        lines.append("📅 <b>Meetings</b>")
        for m in meetings:
            t = time_of(m)
            prefix = t if t else "All day"
            lines.append(f"{prefix} - {title_of(m)}")
        lines.append("")

    # --- Tasks section: grouped by company ---
    if todos:
        by_company = {}
        for t in todos:
            by_company.setdefault(select_of(t, "Company") or "No company", []).append(t)
        lines.append("✅ <b>Tasks due</b>")
        for company in sorted(by_company):
            lines.append(f"🏢 <b>{company}</b>")
            for t in by_company[company]:
                pr = select_of(t, "Priority")
                emoji = PRIORITY_EMOJI.get(pr, "•")
                d = date_of(t)
                overdue = " ⚠️ overdue" if d and d < today else ""
                lines.append(f"  {emoji} {title_of(t)}{overdue}")
            lines.append("")

    return "\n".join(lines).strip()


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=30)
    r.raise_for_status()
    print("Sent Telegram digest.")


def main():
    tasks = query_due_tasks()
    print(f"Found {len(tasks)} due/overdue task(s).")
    send_telegram(build_message(tasks))


if __name__ == "__main__":
    main()
