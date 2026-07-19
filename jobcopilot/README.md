# Job Application Copilot

A **local, laptop-hosted** job-search assistant that keeps *you* in the loop.
Built in the spirit of the trading engine in this repo: an async orchestrator, a
live dashboard, a hard kill switch, and everything running on your own machine.

It does four things:

1. **Parses your `.docx` CV** into structured skills / experience.
2. **Scores any job description** (0–100) against your resume + profile, with a rationale.
3. **Drafts a tailored cover letter and screening-question answers** for each match.
4. **Serves a live dashboard** (dark-mode, iPad-friendly PWA) with a **kill switch**, a review queue, a jobs table, and stats.

## What it does *not* do — and why

It does **not** log into LinkedIn, drive a stealth browser, or auto-submit
applications. That was the original ask, but automated login + submission is
built to evade LinkedIn's bot detection, violates their User Agreement, and gets
accounts **permanently banned** — a real risk to the very asset you're trying to
use. LinkedIn also exposes no compliant jobs-apply API.

So this tool does the slow part — reading the JD, judging fit, writing a tailored
letter, drafting answers — and hands you finished materials. **You** paste them
into LinkedIn's own Easy Apply and click submit. You get the speed and the iPad
dashboard, with none of the ban risk.

## Architecture

```
        ┌──────────────────────── LAPTOP ────────────────────────┐
        │  setup_wizard  ──▶  profile.json      resume.docx       │
        │                                          │              │
        │                                          ▼              │
        │                                  resume_parser ──▶ resume_structured.json
        │                                                         │
        │   FastAPI server (server.py) ── async scoring worker ── │
        │     REST + WebSocket           │        │               │
        │     serves /static dashboard   ▼        ▼               │
        │                       matcher.py     llm.py (Claude,     │
        │                          │            or heuristic)      │
        │                          ▼                               │
        │                  SQLite (applications.db)                │
        │   kill switch: KILL_SWITCH.flag (pauses the worker)      │
        └──────────────────────────┬──────────────────────────────┘
                        LAN / Tailscale / ngrok
                                   ▼
                        iPad Safari  →  dashboard PWA
```

## Setup — the two-step version

No CLI wizard needed. Just start the server and upload your CV from the dashboard:

```bash
cd jobcopilot
./run.sh start                 # macOS/Linux — or double-click shortcuts/macos/Run Copilot.command
#                                Windows: shortcuts\windows\Run Copilot.bat
```

`./run.sh` creates a `venv/`, installs dependencies, bootstraps a default
`profile.json`, and prints the dashboard URL + a QR code. Then, on your iPad
(or laptop):

1. Open the dashboard (scan the QR, or the LAN/Tailscale URL it prints).
2. Go to the **Profile** tab → **Upload & parse CV** (your `.docx`). The copilot
   parses it and **auto-fills your name, title, skills, and target roles**. That's it —
   the Search tab immediately has pre-filtered LinkedIn links, and any job you add
   gets scored.

### Optional: better scoring with an API key

Works out of the box using a local keyword-overlap heuristic (nothing leaves the
laptop). For much better scores and real cover letters, add a Claude key:

```bash
cp .env.template .env          # then paste ANTHROPIC_API_KEY into .env
```

### Optional: CLI wizard

Prefer to set everything up from the terminal instead of the dashboard? Run
`./run.sh setup` (or `shortcuts/*/Setup Profile.*`). It's entirely optional.

### Windows

Double-click the `.bat` files in `shortcuts\windows\`. Same behaviour as the
macOS `.command` files.

## Using it

- **Search** tab: pre-filtered LinkedIn job-search links built from your profile
  (target titles × locations, seniority, date-posted, remote toggle). Tap one and
  LinkedIn opens in your browser — you browse and apply yourself. It only
  *constructs URLs*; it never logs in, scrapes, or submits.
- **Add job** tab: paste a job description (title/company optional). The
  background worker scores it and drafts a cover letter within a few seconds.
- **Review** tab: cards for every match at/above your threshold, best score
  first. Tap **View / copy** to grab the cover letter and answers, apply on
  LinkedIn yourself, then tap **Mark applied** (or **Skip**).
- **All jobs** tab: sortable/filterable table of everything logged.
- **Profile** tab: edit keywords, titles, locations, threshold — no wizard rerun.
- **STOP** button (always visible): engages the kill switch and pauses all
  background scoring. It turns into **RESUME**.

## Kill switch

The kill switch is a flag file, `KILL_SWITCH.flag`, in the project root. When it
exists, the scoring worker pauses. Three ways to trigger it:

- The dashboard **STOP** button (`POST /api/kill`).
- The `KILL` desktop shortcut (offline fallback — double-click anytime).
- `touch KILL_SWITCH.flag` from a terminal.

Remove the flag (RESUME button, or `rm KILL_SWITCH.flag`) to continue.

> There's no browser automation to abort here, so the switch simply pauses
> background LLM work — it can't submit anything on your behalf in the first place.

## iPad access

- **Same Wi-Fi (simplest):** the server binds `0.0.0.0` by default; open the LAN
  URL printed at startup (e.g. `http://192.168.1.20:8000`) in Safari. Share →
  **Add to Home Screen** to install it as a full-screen PWA.
- **Anywhere (recommended): [Tailscale](https://tailscale.com)** — install on
  laptop + iPad, log into the same account, and use the laptop's Tailscale
  hostname instead of the LAN IP. Encrypted, works off your home network, free.
- **ngrok** also works (`ngrok http 8000`) if you prefer a public tunnel.

## Notifications (optional)

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` to get a Telegram ping
when a job clears your threshold, when you mark one applied, and when the kill
switch engages. Leave them blank to disable.

## LLM & privacy

- With `ANTHROPIC_API_KEY` set, scoring and cover letters use Claude
  (`JOBCOPILOT_MODEL`, default `claude-opus-4-8`; set `claude-haiku-4-5` for
  cheaper runs).
- Without a key, everything still works via a local keyword-overlap heuristic —
  rougher scores and template letters, but zero external calls.
- Only the **job description and your resume text** are ever sent to the LLM.
  Your `.env` secrets are never logged or transmitted anywhere else. `.env`,
  `profile.json`, `resume_structured.json`, and `applications.db` are gitignored.

## Files

| Path | Purpose |
|------|---------|
| `jobcopilot/config.py` | Paths, profile load/save, env settings |
| `jobcopilot/db.py` | SQLite schema + helpers |
| `jobcopilot/resume_parser.py` | `.docx` → structured JSON |
| `jobcopilot/llm.py` | Claude calls + heuristic fallback |
| `jobcopilot/matcher.py` | Score a job and persist |
| `jobcopilot/links.py` | Build pre-filtered LinkedIn search URLs |
| `jobcopilot/setup_wizard.py` | Interactive profile builder |
| `jobcopilot/server.py` | FastAPI REST + WebSocket + worker |
| `jobcopilot/orchestrator.py` | Launcher (URL + QR) |
| `jobcopilot/killswitch.py` | Flag-file kill switch |
| `jobcopilot/notify.py` | Optional Telegram |
| `jobcopilot/static/` | Dashboard PWA (HTML/CSS/JS + manifest) |
| `shortcuts/` | macOS `.command` / Windows `.bat` |

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/jobs?status=` | List jobs |
| GET | `/api/stats` | Counts, avg score, kill-switch + LLM state |
| GET | `/api/links?date_posted=&remote_only=` | Pre-filtered LinkedIn search URLs from your profile |
| POST | `/api/jobs` | Add a job (queues it for scoring) |
| POST | `/api/rescore/{id}` | Re-queue a job for scoring |
| POST | `/api/approve/{id}` | Mark applied |
| POST | `/api/reject/{id}` | Mark skipped |
| DELETE | `/api/jobs/{id}` | Delete a job |
| POST | `/api/kill` / `/api/resume` | Toggle the kill switch |
| GET/PUT | `/api/profile` | Read / update profile |
| GET | `/api/resume` | Parsed-resume summary |
| POST | `/api/resume/upload` | Upload a `.docx` CV (multipart); parses + auto-fills profile |
| WS | `/ws/live` | Live snapshot + events |
