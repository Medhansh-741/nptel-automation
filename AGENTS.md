# NPTEL Course Automation Pipeline — Agent Operating Manual

This file is auto-loaded by opencode (and Claude Code) into every session started in this repo. It is the operating manual for running the NPTEL course automation. **Read it fully before any tool use.**

## What this is

An assisted pipeline that completes NPTEL SWAYAM weekly assignments for the course in `.env` (`NPTEL_COURSE_ID`):

- **Programming Assignments (PA)** — read the problem → write Java → inject into the ACE editor → Compile & Run → verify → submit.
- **Image-based Quiz (MCQ)** — the question text + all options live *inside a PNG*. Extract → OCR with a local vision model → reason → fill radios → submit.

**A session = YOU (the agent) driving a Playwright MCP browser + running scripts.** No full automation script; the intelligence is the assistant following this manual step by step.

## Critical ground rules

1. **STOP-AND-REPORT rule (hard requirement):** if anything unexpected appears (page divergence, unexpected error, ambiguous quiz question, submission rejected) → STOP, report to the user, and ask. NO silent retry loops, NO guessing answers.
2. **Use the Playwright MCP browser, NOT chrome-devtools MCP.** The Playwright MCP browser is configured with a persistent profile (`BROWSER_PROFILE_DIR`) that holds the live authenticated session. The chrome-devtools MCP browser is **unauthenticated** (shows a login/preview page) — never use it.
3. **Never write `state.json`** except on an authenticated course page. `state.json` is the Playwright storageState snapshot; the live session actually lives in the browser profile dir.
4. **Never commit**: `.env`, `state.json`, `db/answers.db`, images. All covered by `.gitignore`.
5. All course/assignment IDs are **discovered at runtime** from the course outline URLs — do not hardcode week IDs.

## Environment / config

- `run.ps1` loads `.env`, ensures Ollama is up, validates the model + DB, then hands off. Run it first.
- `.env` keys are read by `scripts/ocr.py` and `scripts/db_log.py` automatically.
- OCR model: `OLLAMA_MODEL` (default `glm-ocr-tuned`). Create once: `ollama create glm-ocr-tuned -f Modelfile`.

## Repo layout

```
AGENTS.md             <- this operating manual (auto-loaded)
Modelfile             <- tuned OCR model definition (public)
run.ps1               <- launcher: Ollama + env validation
.env / .env.example   <- device config (git-ignored)
docs/README.md        <- human-facing install/usage
docs/plan.md          <- the phase plan (reference)
docs/ocr.md           <- OCR pipeline decision log
db/schema.sql         <- schema source of truth; answers.db is generated+ignored
scripts/ocr.py        <- OCR images -> text with SQLite caching (NDJSON-safe)
scripts/db_log.py     <- log submissions / run events / list rows
scripts/snippets/browser.txt  <- proven Playwright run_code_unsafe snippets
```

## URL & ID discovery

- Course page: `https://onlinecourses.nptel.ac.in/e-learning/course/<course_id>` (course_id from `.env`).
- Each week = a `unitId`. Click the week's heading in the sidebar outline → the URL becomes `?unitId=<u>`.
- The outline items are **buttons, not anchors — they have no `href`**. To discover each assignment/quiz ID: **click the item, then read `location.href`** — it updates to the item's URL (snippet 5 in `scripts/snippets/browser.txt`).
- **PA URL:** `?unitId=<u>&progassignmentId=<id>`
- **Quiz URL:** `?unitId=<u>&assessmentId=<id>`

## Programming Assignment (PA) flow

For each assignment:

1. Navigate to the PA URL (`progassignmentId`).
2. Read the problem statement (visible text + starter code). Record it.
3. **Solve it in Java** (you are the reasoning layer). Mind the OUTPUT FORMAT (see gotchas).
4. Inject the solution into the correct ACE editor (snippet 2):
   - Each PA has up to 3 editors: `prefix-editor`, `code-editor`, `suffix-editor`.
   - Inject with: `window.ace.edit('<id>').getSession().setValue(code)` then `editor._emit('input', {})` then dispatch a bubbled `input` event on `editor.textInput.getElement()`.
   - **`fireEvent` does NOT exist** — using it throws. Use the `_emit` pattern verbatim from the snippet.
5. Click **Compile & Run**. Wait for the **Evaluation Results** region.
6. Verify public/private test results. If a test fails → diagnose, fix, re-inject, re-run (max 3 attempts, then STOP + report).
7. On pass → **Submit**. Confirm the "Thank you!" dialog, then close it.
8. Log with `scripts/db_log.py submit ...` and `scripts/db_log.py log --event PH3-PA<name> ...`.

### PA gotchas (learned the hard way)

- **Output labels:** NPTEL's checker often requires a text prefix, not a bare value. Real cases from past weeks:
  - `System.out.println("<Label> is: " + obj.field);`
  A bare value (`println(obj.field)`) fails the public test. Read the problem statement / sample test cases for the expected output format (the prefix text must match exactly).
- Sometimes you must add a missing getter/method (e.g. `public int getX() { return x; }`) rather than edit the main body.

## Quiz flow (image-based MCQ)

1. Navigate to the quiz URL (`assessmentId`).
2. **Extract all question images** (snippet 1): each question = one `<section class="bg-white">` containing one `<img src="data:image/png;base64,...">` that holds the **question + all options inside the image**. The DOM radios are just bare `a.`–`d.` placeholders with no text.
3. Save the images to a temp dir via the snippet, then run: `python scripts/ocr.py <tmp_dir>` — it OCRs each PNG (live) or uses the SQLite cache, printing `question + options` per image.
4. **Reason the answer** for each question from the OCR text. For any genuinely ambiguous question → STOP + report (no guessing).
5. Fill radios with snippet 3: map letter → index `a:0, b:1, c:2, d:3`, click + dispatch `change`/`input`.
6. **Verify ALL 10 radios are checked** (snapshot or evaluate). The direct `.click()` on React radios is unreliable — any straggler must be clicked via a **real mouse click on its `<label>`** (see snippet 3 note), then re-verify.
7. Click **Submit Answers**, wait for the "Thank you!" dialog, close it.
8. Log with `scripts/db_log.py submit --type quiz --ref "assessmentId=<id>" ...`.

## Harmless errors — DO NOT STOP on these

The NPTEL page always logs these console errors; they are benign and the flows work anyway:

- `Failed to load resource ... 404` for `/e-learning/course/snippets/java.js`
- `Refused to execute script ... 'theme-tomorrow.js' because its MIME type ('text/html') is not executable`
- `Unable to infer path to ace from script src ... ace.config.set('basePath'...)`
- YouTube `postMessage` origin mismatch warnings
- Occasional `500` on `programming_assessment` API — retry once, usually succeeds

## Verification

- **Progress indicator:** the sidebar count (`(N of T)`, where T = total items) is authoritative; the **percentage text lags** (e.g. shows a stale percentage while the count already says all done). Trust the count.
- Confirm the "Your last recorded submission was on ..." line on re-open, or the "Thank you!" dialog after submit.

## Session playbook (order of operations)

1. `powershell -ExecutionPolicy Bypass -File .\run.ps1` → confirm Ollama + model + DB.
2. Open the course page in the Playwright MCP browser. Confirm authenticated (sidebar progress visible, NOT a login/preview page). If expired → STOP + ask user to sign in once in the browser.
3. Inventory: parse the outline for the target week → list pending PA + quiz IDs.
4. Execute the PA flow for each pending assignment, then the quiz flow, logging each step.
5. Verify final progress; update `docs/plan.md` checkboxes and `docs/ocr.md` decision log.
