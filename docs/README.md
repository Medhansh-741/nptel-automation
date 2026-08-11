# NPTEL Course Automation Pipeline

Automated completion of **NPTEL SWAYAM weekly assignments** (Programming Assignments + image-based MCQ quizzes) using a local OCR model and a browser-automation assistant.

> **What it does:** For a chosen week, the assistant (opencode) reads each programming problem, writes the Java solution, injects it into the portal's ACE editor, runs and verifies it, then submits. For the weekly quiz, it OCRs the question images with a local GLM vision model, reasons the answers, fills the radios, and submits. Everything is logged to a local SQLite database.

> **Warning:** This automates answering assignments on a proctored platform. Use only for your own NPTEL account and in line with the course's academic-integrity policy.

---

## How it works (3 layers)

```
                 ┌─────────────────────────────────────┐
                 │      USER  "Run Week 5"             │
                 └──────────────────┬──────────────────┘
                                    │
                                    v
                 ┌─────────────────────────────────────┐
                 │  run.ps1   pre-flight checks        │
                 │  Ollama up · OCR model · DB ready   │
                 └──────────────────┬──────────────────┘
                                    │
      ┌─────────────── LAYER 1 — AUTH (persistent session) ───────────────┐
      │  Playwright MCP browser · BROWSER_PROFILE_DIR · signed in once    │
      └─────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    v
      ┌────────────── LAYER 2 — MECHANICS (browser + scripts/) ──────────┐
      │  auth check → inventory (parse outline → IDs)                    │
      └────────────────────────────┬─────────────────────────────────────┘
                                    │
   ┌────────────────────────────────┴──────────────────────────────┐
                 v                                  v               
   ┌────────────────────────────┐     ┌────────────────────────────┐
   │  PROGRAMMING ASSIGNMENTS   │     │  QUIZ  (image-based MCQ)    │
   │  (x5, one at a time)       │     │                            │
   ├────────────────────────────┤     ├────────────────────────────┤
   │ 1 read problem + starter   │     │ 1 extract base64 PNGs      │
   │   code                     │     │ 2 scripts/ocr.py → glm-ocr │
   │ 2 write Java  ◄ L3 brain   │     │   (SQLite-cached)          │
   │ 3 inject into ACE editor   │     │ 3 reason answers ◄ L3 brain│
   │ 4 Compile & Run            │     │ 4 fill radios (snippet 3)  │
   │ 5 verify tests (≤3 retry)  │     │ 5 verify all 10 checked    │
   │ 6 Submit → "Thank you!"    │     │ 6 Submit → "Thank you!"    │
   └──────────────┬─────────────┘     └──────────────┬─────────────┘
                  └──────────────────┬────────────────┘
                                     │
                                     v
      ┌────────────── LAYER 3 — INTELLIGENCE (opencode assistant) ──────┐
      │  verify progress (sidebar COUNT is truth — the % lags)          │
      └─────────────────────────────┬───────────────────────────────────┘
                                     │
                                     v
                 ┌─────────────────────────────────────┐
                 │  scripts/db_log.py → answers.db     │
                 │  submissions · run_log · ocr_cache  │
                 └─────────────────────────────────────┘
```

There is no monolithic script. A session is the assistant following `AGENTS.md` (the operating manual, auto-loaded) step by step, calling browser tools + `scripts/`. The diagram above is the whole cycle in one glance: a user prompt → `run.ps1` pre-flight → the persistent browser session (Layer 1) → the browser/scripts doing the work (Layer 2) → the assistant's reasoning and verification (Layer 3) → an audit trail in `answers.db`.

---

## Prerequisites

- **Windows 10/11** (PowerShell 5.1+). Non-Windows users can run the scripts directly; only `run.ps1` is PowerShell.
- **Python 3.10+** (stdlib only — no pip packages needed).
- **Ollama** running locally, with a vision model. Default: `glm-ocr` (2.2 GB, free, local).
- **opencode** (or another coding agent that supports the Playwright MCP server).

---

## Setup (first time, ~5 minutes)

1. **Clone & enter the repo**
   ```powershell
   git clone <this-repo-url> nptel && cd nptel
   ```

2. **Configure your device** — copy the template and fill in your values:
   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```
   The two critical values:
   - `BROWSER_PROFILE_DIR` → a path where your Chrome profile will live (the live NPTEL session).
   - `OLLAMA_MODEL` → the OCR model name (default `glm-ocr-tuned`).

3. **Create the tuned OCR model** (once)
   ```powershell
   ollama create glm-ocr-tuned -f Modelfile
   ```
   (Requires the base `glm-ocr` model: `ollama pull glm-ocr`.)

4. **Initialize the database** (creates `db/answers.db` from `db/schema.sql`)
   ```powershell
   python -c "import sqlite3,glob,os; db=sqlite3.connect('db/answers.db'); db.executescript(open('db/schema.sql').read()); db.commit(); print('db ready')"
   ```

5. **Register the Playwright MCP server in opencode** — point it at `BROWSER_PROFILE_DIR`:
   ```jsonc
   // in ~/.config/opencode/opencode.jsonc  (or .opencode/opencode.jsonc in this repo)
   {
     "mcp": {
       "playwright": {
         "type": "local",
         "command": ["npx", "@playwright/mcp@latest", "--user-data-dir=C:\\path\\to\\your\\profile"]
       }
     }
   }
   ```

6. **Sign in once** — open `https://onlinecourses.nptel.ac.in` in the Playwright MCP browser and log in. The session persists in the profile; you only redo this when it expires (roughly monthly).

---

## Running a week

1. **Launch checks**
   ```powershell
   .\run.ps1
   ```
   Confirms Ollama, the OCR model, and the DB are ready.

2. **Open a chat with the assistant in this repo** and say, e.g.:
   > "Run Week 5 for the course in .env."

3. The assistant follows `AGENTS.md`: auth check → inventory (parse the course outline for the week's unit) → submit each Programming Assignment → OCR + answer the quiz → verify progress → log everything.

---

## What gets logged & stored

| File | Contents | Committed? |
|---|---|---|
| `db/answers.db` | OCR cache (image→text), submissions, run log | **No** (per-user data) |
| `state.json` | browser session snapshot | **No** (credentials) |
| `.env` | device-specific config | **No** |
| `.playwright-mcp/` | runtime snapshots | **No** |
| `db/schema.sql` | table definitions | Yes |
| `docs/*` | README, plan, OCR decision log | Yes |
| `scripts/*` | OCR + logging helpers, browser snippets | Yes |

---

## Project layout

```
AGENTS.md                  operating manual (auto-loaded into assistant sessions)
Modelfile                  OCR model definition
run.ps1                    launcher (Ollama + env + DB checks)
.env.example               config template (copy → .env)
db/schema.sql              SQLite schema (source of truth)
scripts/ocr.py             OCR images → text, SQLite-cached (NDJSON-safe)
scripts/db_log.py          log submissions / run events / list rows
scripts/snippets/browser.txt  proven Playwright code snippets
docs/plan.md               the phased plan (reference)
docs/ocr.md                OCR pipeline decision log
```

---

## Security

- `state.json` and `.env` contain sensitive info — the `.gitignore` keeps them out of any commit. Do not force-add them.
- The DB contains your assignment answers — keep it local.
- Verify the `BROWSER_PROFILE_DIR` points to a private directory on your machine.

## Troubleshooting

- **"Model 'glm-ocr-tuned' not found"** → run `ollama create glm-ocr-tuned -f Modelfile`.
- **Browser shows a login/preview page** → session expired. Sign in once in the Playwright MCP browser.
- **OCR returns nothing** → confirm Ollama is running (`ollama serve`) and the model is loaded.
- **Page console errors** → see the "Harmless errors" section in `AGENTS.md`; most are benign portal noise.
