# Command Center Automation — Setup Guide (Phase 1)

Two automations, both running free on GitHub Actions (no server):

1. **Notion → Google Calendar** — meetings you add in Command Center (tasks tagged
   **Meeting** with a Date) appear in a dedicated Google Calendar within ~15 min.
2. **Telegram reminders** — a digest of what's due today/overdue, sent to Telegram
   twice a day (07:00 and 13:00 Asia/Jakarta).

Work top to bottom. Budget ~30 minutes the first time.

---

## What you'll collect (8 secrets)

Keep these in a scratch note as you go; you paste them into GitHub at the end.

| Secret | Where it comes from |
|---|---|
| `NOTION_TOKEN` | Notion integration (Step 2) |
| `NOTION_TASKS_DB_ID` | Already known: `7871c7c52c268328b5dc0191a692671d` (Step 2) |
| `GOOGLE_CLIENT_ID` | Google OAuth client (Step 3) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client (Step 3) |
| `GOOGLE_REFRESH_TOKEN` | `get_google_token.py` (Step 3) |
| `GOOGLE_CALENDAR_ID` | Dedicated Google Calendar (Step 4) |
| `TELEGRAM_BOT_TOKEN` | BotFather (Step 5) |
| `TELEGRAM_CHAT_ID` | getUpdates (Step 5) |

---

## Step 1 — Create the GitHub repo & upload files

1. Sign in / create a free account at github.com.
2. New repository → name it e.g. `command-center-automation` → **Private** → Create.
3. **Unzip the package on your computer first**, then upload its contents:
   - On the new empty repo page, click the link **"uploading an existing file"**
     (or the **Add file → Upload files** button).
   - Drag the UNZIPPED files into the dashed box, then click **Commit changes**.

**What to upload vs. keep local:**
- ✅ Upload: `notion_to_gcal.py`, `telegram_reminder.py`, `requirements.txt`,
  `.github/workflows/gcal-sync.yml`, `.github/workflows/telegram-reminders.yml`
- ✅ Optional (harmless): `get_google_token.py`, `SETUP.md`
- ⛔ NEVER upload: `client_secret.json` (your Google credentials — keep it only on
  your computer while running the token helper in Step 3).

> The `.yml` files MUST end up inside `.github/workflows/`. If drag-and-drop doesn't
> keep the folders, create them manually: **Add file → Create new file**, type the
> path `.github/workflows/gcal-sync.yml` (the slashes make the folders), paste the
> contents, Commit. Repeat for `telegram-reminders.yml`.

---

## Step 2 — Notion integration + database id

**Token:**
1. Go to notion.so/my-integrations → **New integration**.
2. Name it "Command Center Automation", pick your workspace, submit.
3. Copy the **Internal Integration Secret** → this is `NOTION_TOKEN`.

**Give it access to the Tasks database:**
4. Open the **Tasks** database (inside Command Center 3) → top-right **•••** →
   **Connections** → **Connect to** → choose your new integration.

**Database id:**
5. `NOTION_TASKS_DB_ID` is already known — your Tasks database:
   `7871c7c52c268328b5dc0191a692671d`
   (This is the database ID, confirmed from Notion. Do NOT use the data-source id
   `ad51c7c5...`.)

---

## Step 3 — Google Auth Platform (client + refresh token) + PUBLISH

> NOTE: Google renamed "OAuth consent screen" to **Google Auth Platform** in 2024.
> Older guides that mention "OAuth consent screen" mean this. Its settings live in
> four tabs: **Branding, Audience, Data Access, Clients**.

1. Go to console.cloud.google.com → create a project (e.g. "Command Center").
   Make sure this project is selected in the project picker at the top.
2. **APIs & Services → Library →** search **Google Calendar API →** Enable.
   (The Google Auth Platform menu only appears AFTER an API is enabled.)
3. **APIs & Services → Google Auth Platform** → if you see "Google Auth Platform
   not configured yet", click **Get Started**. Complete the short wizard:
   - **App Information:** App name (e.g. "Command Center"), User support email (pick
     your address from the dropdown)
   - **Audience:** choose **External**
   - **Contact Information:** your email
   - **Acknowledgement:** agree → Create
   (Direct link: console.cloud.google.com/auth/branding — right project selected.)
4. **PUBLISH THE APP (stops your token expiring):**
   Go to the **Audience** tab (console.cloud.google.com/auth/audience). Under
   **Publishing status**, if it says "Testing", click **PUBLISH APP** → confirm, so
   status becomes **In production**. No Google verification is needed for a personal
   app only you use. (Tokens left in "Testing" expire after 7 days; published ones
   keep working.)
5. **Create the OAuth client:** go to the **Clients** tab
   (console.cloud.google.com/auth/clients) → **Create client** → Application type
   **Desktop app** → Create.
6. **Download JSON.** Save it as `client_secret.json` next to `get_google_token.py`
   on your computer.
7. In a terminal on your computer:
   ```
   pip install google-auth-oauthlib
   python get_google_token.py
   ```
   A browser opens. If you see "Google hasn't verified this app", that's expected
   for a personal app — click **Advanced → Go to Command Center (unsafe)** and
   continue (it's your own app, your own calendar). Sign in → Allow. The script
   prints:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
   Copy all three.

   > If `GOOGLE_REFRESH_TOKEN` is blank: go to myaccount.google.com/permissions,
   > remove the app, and run the script again.

---

## Step 4 — Dedicated Google Calendar

1. In Google Calendar (web) → left sidebar → **Other calendars → + → Create new
   calendar** → name it "Command Center" → Create.
2. Open that calendar's **Settings** → scroll to **Integrate calendar** →
   copy **Calendar ID** (looks like `abcd...@group.calendar.google.com`).
   This is `GOOGLE_CALENDAR_ID`.

---

## Step 5 — Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → follow prompts.
   It gives a token like `123456:ABC-DEF...` → this is `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot (e.g. "hi") so it has a chat to reply to.
3. In a browser open:
   `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   Find `"chat":{"id": 123456789 ...}` — that number is `TELEGRAM_CHAT_ID`.

---

## Step 6 — Paste secrets into GitHub

1. Your repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. Add all 8 secrets from the table above, one at a time (exact names, no quotes).

---

## Step 7 — Test

1. Repo → **Actions** tab. If prompted, enable workflows.
2. Add a test meeting in Notion first: a task named "Test meeting", Date with a time
   range, Tag = **Meeting**, any Company.
3. Click **Notion to Google Calendar sync → Run workflow**. Then check your
   Command Center Google Calendar — the event should appear.
4. Click **Telegram reminders → Run workflow**. You should get a Telegram message.
   (If nothing is due today, it says "Nothing due today.")

After the manual test passes, the schedules take over automatically:
- Calendar sync: every 15 minutes
- Reminders: 07:00 and 13:00 Asia/Jakarta

---

## How you use it day to day

- **Add a meeting:** new task in Command Center → Name, Date (with time range),
  Tag = **Meeting**, Company. It lands in Google Calendar within ~15 min.
- **Add a task:** new task with a **Date** and Status. If due today/overdue, it
  shows in your next Telegram digest.

---

## Notes & limits (honest)

- **One-way** (Notion → Google). Editing a meeting in Notion updates the Google
  event on the next run. **Deleting** a meeting in Notion does NOT remove it from
  Google (Phase 1 is create+update only). Delete stray events in Google directly.
- **~15 min delay**, not instant.
- **Token longevity:** with the app PUBLISHED (Step 3.4) and the sync running every
  15 min, your Google refresh token will not expire under normal use. It would only
  stop if you revoke access, or if unused for 6 months (won't happen here). If it
  ever stops, re-run `get_google_token.py` once.
- **Property names matter.** The scripts expect these exact Tasks properties:
  `Name`, `Date`, `Tags` (with a "Meeting" option), `Company`, `Status`,
  `Priority`, `Archive`. If you rename any, update the scripts.

---

## Phase 2 (later)

Add meetings/tasks *by texting the Telegram bot* (e.g.
`/meeting Ms Christy, Jul 10 10-12pm, Above & Beyond`). Built on this same repo;
adds a polling job that reads your messages and writes to Notion. Do this once
Phase 1 is proven.

---
---

# PHASE 2 — Add meetings & tasks by texting the bot (natural language)

Text your bot naturally; Gemini (free) parses it; you confirm with buttons; it's
written to Command Center. Meetings then flow to Google Calendar via Phase 1.
Also includes **Phase 1.5**: marking a meeting Done or Archived in Notion removes
its Google Calendar event on the next sync.

## Extra secrets for Phase 2

| Secret | Where it comes from |
|---|---|
| `GEMINI_API_KEY` | aistudio.google.com/apikey → Create API key (free) |
| `NOTION_PROJECTS_DB_ID` | Your Projects database id: `0151c7c52c2683109b1a011d987f9baf` |

Add both in **Settings → Secrets and variables → Actions** like the others.

> `NOTION_PROJECTS_DB_ID` lets the bot link a task to a project you mention.
> Also make sure your Notion integration is connected to the **Projects** database
> too (Projects DB → ••• → Connections → your integration), not just Tasks.

## New files to upload (in addition to Phase 1 files)

- `gemini_parser.py`
- `telegram_bot.py`
- `state.json`  (starter file — the bot updates it automatically)
- `.github/workflows/telegram-bot.yml`

## How to use it

Just text your bot, one or several at once, e.g.:
- "meeting with Ms Christy Jul 10 10-12 at the therapy center"
- "review payroll friday, high priority, felindo, warehouse ops project"
- "call supplier tomorrow 2pm and board meeting jul 15 church"

Within ~5 min the bot replies with a numbered list and buttons:
`[✅ Add all] [❌ Cancel]` and `[Add 1] [Add 2] ...`
Tap to confirm. Confirmed items appear in Command Center (meetings tagged
Meeting → Google Calendar within ~15 min).

Send `/help` anytime for a reminder.

## Notes & limits (Phase 2)

- **~5 min delay** each direction (polling). Not instant.
- **Gemini free tier:** Flash model, plenty for personal use. Google may use free-
  tier inputs to improve their products — keep genuinely confidential details out
  of the bot. Model name is set in the workflow (`GEMINI_MODEL`); swap if Google
  renames it.
- **Confirmation is required** before anything is written — nothing is added until
  you tap a button.
- **State:** the bot stores its read-position and pending items in `state.json`,
  which the workflow commits back to the repo each run. Don't hand-edit it.
- **Project linking** is fuzzy — if it guesses wrong or finds nothing, the item is
  still added, just without a project (link it in Notion). Mention the project name
  clearly to improve matching.
- **Phase 1.5:** to remove a meeting from Google Calendar, set its Status to Done
  or tick Archive in Notion — the next calendar sync deletes the event. (Deleting
  the Notion page outright still leaves the Google event; use Done/Archive instead.)
