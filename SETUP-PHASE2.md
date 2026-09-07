# Phase 2 Setup — Add meetings & tasks by texting the bot

You've finished Phase 1 (Google Calendar sync + Telegram reminders). This guide
adds two things on top, using the SAME repo:

- **Phase 2** — text your bot naturally ("meeting with Ms Christy Jul 10 10-12 at
  the therapy center"); Gemini parses it; you confirm with buttons; it lands in
  Command Center (meetings then flow to Google Calendar via your Phase 1 sync).
- **Phase 1.5 + cancellation** — marking a meeting **Done**, **Cancelled**, or
  **Archived** in Notion removes its Google Calendar event on the next sync.
  **Rescheduling** already works: change the Date in Notion and the Google event
  moves automatically (no extra setup).

Budget ~15 minutes.

---

## Step 0 — One manual Notion change (30 seconds)

The API can't edit Status options, so add the Cancelled status yourself:

1. Open the **Tasks** database.
2. Click the **Status** column header → **Edit property** (or open any task's
   Status field → **Edit**).
3. Under the **Complete** group → **+ Add option** → type **Cancelled** → pick a
   colour → done.

Now Done / Cancelled / Archive all mean "remove from Google Calendar."

---

## Step 1 — Get the new files into your repo

Add these files (they're in the updated package) to your existing repo and push:

- `gemini_parser.py`
- `telegram_bot.py`
- `state.json`   (starter file; the bot updates it automatically — don't hand-edit)
- `.github/workflows/telegram-bot.yml`
- (updated) `notion_to_gcal.py`  — now handles Done/Cancelled/Archive removal
- (updated) `telegram_reminder.py` — now ignores Cancelled tasks
- (updated) `requirements.txt`

From your command line, in the repo folder:
```
git add .
git commit -m "Add Phase 2 bot + cancellation handling"
git push
```

---

## Step 2 — Two new secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value / where |
|---|---|
| `GEMINI_API_KEY` | Your key from aistudio.google.com/apikey (starts `AIza...`) |
| `NOTION_PROJECTS_DB_ID` | `0151c7c52c2683109b1a011d987f9baf` |

> `NOTION_PROJECTS_DB_ID` lets the bot link a task to a project you mention.

---

## Step 3 — Connect the integration to the Projects database

Your Notion integration is already connected to **Tasks**. Do the same for
**Projects** so the bot can read your project list:

1. Open the **Projects** database (inside Command Center 3).
2. Top-right **•••** → **Connections** → **Connect to** → your
   "Command Center Automation" integration.

(If you skip this, tasks still get added — just without project links.)

---

## Step 4 — Test

1. Repo → **Actions** → enable workflows if prompted.
2. In Telegram, send your bot:
   `meeting with Test Person tomorrow 3-4pm at the therapy center`
3. Run **Telegram bot (inbound) → Run workflow** (or wait up to 5 min for the poll).
4. The bot replies with a numbered item + buttons:
   `[✅ Add all] [❌ Cancel]` `[Add 1]`
5. Tap **✅ Add all**. Within ~5 min it confirms "Added 1 item".
6. Check Command Center → the meeting is there, tagged Meeting. Within ~15 min it
   also appears in your Google Calendar (via the Phase 1 sync).

Test cancellation:
- Set that meeting's Status to **Cancelled** in Notion → next calendar sync removes
  the Google event.

Test rescheduling:
- Change its Date in Notion → next sync moves the Google event to the new time.

---

## How you use it day to day

Text the bot naturally, one or several at once:
- "meeting with Ms Christy Jul 10 10-12 at the therapy center"
- "review payroll friday, high priority, felindo, warehouse ops project"
- "call supplier tomorrow 2pm and board meeting jul 15 church"

It shows what it understood with buttons; you tap to confirm. Send `/help` anytime.

---

## Notes & limits

- **~5 min delay** each way (polling).
- **Confirmation required** — nothing is written until you tap a button.
- **Gemini free tier:** Flash model; Google may use free-tier inputs to improve
  their products, so keep genuinely confidential details out of the bot.
- **Project matching is fuzzy** — wrong/again no match just means the item is added
  without a project (link it in Notion). Name the project clearly to help.
- **State** lives in `state.json`, committed back to the repo each run. Don't edit it.
- **Removing a meeting from Google Calendar:** set Status = Done or Cancelled, or
  tick Archive. (Deleting the Notion page outright still leaves the Google event.)
- **Rescheduling** needs no action beyond changing the Date in Notion.

---

## Phase 3 (someday, optional)

Cancel/reschedule EXISTING items by texting the bot ("cancel my meeting with
Christy", "move the board meeting to Friday 2pm"). Deferred — it needs a lookup +
disambiguation layer on top of Phase 2. Revisit once Phase 2 feels solid.
