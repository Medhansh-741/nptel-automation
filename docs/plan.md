# Plan — NPTEL Weekly Assignment Automation Pipeline

**Status:** Approved template (parameterized per target week).
**Target outcome:** Complete a week's items (programming assignments + quiz), all verified, all documented.
**Rule:** If anything unexpected appears → STOP, report, and ask. No silent loops, no guessing.

---

## 1. Context & Current State

### Environment
- OS: Windows 11, shell: PowerShell 5.1
- Working dir: repo root (config via `.env`, git-ignored)
- Python 3.14.0, Node v24.11.0 present; **Playwright for Python NOT installed** (by design — we use MCP browser + Chrome)
- Ollama at `127.0.0.1:11434`, model `glm-ocr:latest` (2.2 GB, local, free) for OCR
- Reasoning: opencode assistant (DeepSeek V4 Flash) — "the worker"; the pipeline is the conveyor belt

### Files present (inventory)
| File | Purpose |
|---|---|
| `state.json` | Playwright storageState snapshot (session cookies; git-ignored). Re-authed periodically → valid ~1 month. |
| `ocr.md` | Decision log for OCR pipeline (checkpoints 1–8). Checkpoint 7 = OFF. |
| `.playwright-mcp` | MCP browser runtime data. |

### Course / platform facts (learned in prior sessions)
- NPTEL course from `.env` (`NPTEL_COURSE_ID`). Login = university Google account (stored in the browser profile; never committed) via Google OAuth.
- Course outline URL pattern: `https://onlinecourses.nptel.ac.in/e-learning/course/<course_id>?unitId=<u>&progassignmentId=<id>` / `&assessmentId=<id>` — **unitId is per-week and discovered at runtime**.
- **Per target week:**
  - 5 programming assignments (PA1…PA5) → each has a `progassignmentId`
  - 1 quiz → has an `assessmentId` (image-based MCQ, all options are base64 PNGs)
- Text assignments are solved in an **ACE editor** (`target.session.setValue(...)` + fire `input` event), then **Compile & Run** → wait for **Evaluation Results** → submit.
- Quiz questions are image-only: question text + answer options are `<img src="data:image/png;base64,...">`. **No DOM text** → must OCR.
- Progress is read from the sidebar progress indicator on the course page.

---

## 2. Architecture (3 layers)

```
┌────────────────────────────────────────────────────────────┐
│ LAYER 3 — INTELLIGENCE  (opencode assistant = worker)       │
│   • Reads problem text (PA) → writes Java solution          │
│   • OCR output (quiz) → reasons MCQ answers                 │
│   • Never scripted; the human-in-the-loop brain            │
├────────────────────────────────────────────────────────────┤
│ LAYER 2 — MECHANICS (automated, verifiable)                │
│   • Session validation & reload                            │
│   • Pending-item inventory (course outline parse)          │
│   • Per-item dispatch: fetch → solve → inject → run → verify → submit → log │
│   • Quiz: extract base64 → GLM-OCR → fill radios → submit  │
├────────────────────────────────────────────────────────────┤
│ LAYER 1 — AUTH (persisted session)                         │
│   • state.json (Playwright storageState) loaded each run   │
│   • GUARDRAIL: never write state.json on login/redirect page │
│   • One-time interactive re-login when expired             │
└────────────────────────────────────────────────────────────┘
```

### Auth reality (documented so we never mis-plan)
- **Google OAuth sessions are NOT permanent.** Cookies expire; `state.json` is a snapshot, valid ~weeks–month.
- Google blocks fully automated login (CAPTCHA/2FA/device checks). **Re-login = human in the loop**: pipeline stops, opens headed Chrome, user signs in (~20 s), state saved back.
- Guardrail rule: only save `state.json` AFTER confirming we are on an authenticated course page (not on `accounts.google.com` or a login/preview redirect). Saving on a login page overwrites good cookies with anonymous ones → destroys recovery.

---

## 3. Phased Plan

> Each phase has: GOAL · STEPS · VERIFY · DONE-WHEN. Advance only when the phase's DONE-WHEN is met. If blocked → STOP and report.

---

### PHASE 0 — Guardrails & baseline (no changes to the live course)

**GOAL:** Prove everything works before touching the live course. Nothing submitted.

- [x] 0.1 Create the deliverable scaffolding files:
  - `Modelfile` for `glm-ocr` (see §5) — bake `PARAMETER num_ctx 16384`, `PARAMETER temperature 0`, `SYSTEM "Text Recognition:"`.
- [x] 0.2 Create `answers.db` (SQLite) schema — image_hash → ocr_text → answer → verified flag → timestamp (see §5).
- [x] 0.3 Create `run.ps1` launcher (see §5).
- [x] 0.4 Baseline snapshot: open course page, record current progress value and the list of the target week's items exactly as rendered.
- [x] 0.5 Session health check: confirm logged-in state renders (no redirect to preview/login). Do NOT resave state unless it was reloaded.

**VERIFY:** `Modelfile` builds (`ollama create glm-ocr -f Modelfile`); `answers.db` exists with schema; baseline progress recorded in log; session confirmed live.
**DONE-WHEN:** Scaffolding verified + baseline recorded + session confirmed live. → PHASE 1

---

### PHASE 1 — Build `glm-ocr` tuned model

**GOAL:** A local OCR model with identical behavior to proven settings but simpler calls.

- [x] 1.1 Write `Modelfile` in working dir.
- [x] 1.2 `ollama create glm-ocr -f Modelfile` (creates a tagged variant; keeps base `glm-ocr` untouched as fallback).
- [x] 1.3 Smoke test: send ONE known image (reuse a captured quiz image or `assignment-view.png`) via `POST /api/generate` with `{"model":"glm-ocr","images":[base64],"prompt":"Text Recognition:","options":{"num_ctx":16384,"num_predict":8192}}`. Confirm readable text out.
- [ ] 1.4 Check `OLLAMA_KEEP_ALIVE` plan: run `ollama serve` with `OLLAMA_KEEP_ALIVE=-1` so the model stays loaded during the quiz session (faster).
- [x] 1.5 Record result in `ocr.md` checkpoint log (add verified run stats).

**VERIFY:** OCR output on test image is readable and matches expected text.
**DONE-WHEN:** Tuned model serves correct OCR on the smoke test. → PHASE 2

---

### PHASE 2 — Session bootstrap + inventory automation

**GOAL:** Reliable start: auth check → pending-item list → dispatch queue. No submission.

- [x] 2.1 Launcher flow (headed Chrome via MCP browser):
  - Load `state.json` → open course unit page (target week's `unitId`, discovered from the outline).
- [x] 2.2 Auth check:
  - If authenticated (progress sidebar visible) → continue.
  - If redirected to `/preview/`, `login`, `accounts.google.com` → STOP, report "session expired", open headed OAuth, ask user to sign in, then save state ONLY after confirming authenticated page.
- [x] 2.3 Parse course outline for the target week's `unitId` → enumerate pending items: 5 PA (names + `progassignmentId`s) + 1 quiz (`assessmentId`). Save the exact item list to the run log.
- [x] 2.4 Mark each item's status: not-started / in-progress / done (from DB cache + progress).

**VERIFY:** Item list in run log matches the 6 expected items; statuses correct.
**DONE-WHEN:** Dispatch queue built and logged; auth confirmed. → PHASE 3

---

### PHASE 3 — Target-Week Programming Assignments (PA1 → PA5)

> Run items in order PA1, PA2, PA3, PA4, PA5. Each item is a self-contained mini-flow.

**Per-assignment mini-flow:**
- [x] 3.x.1 Open the assignment unit page (its `unitId` / `progassignmentId` URL).
- [x] 3.x.2 Read the problem statement (question text + starter code if any). Record in log.
- [x] 3.x.3 SOLVE (Layer 3): write Java solution meeting the problem. Verify against sample I/O mentally / by reasoning.
- [x] 3.x.4 Inject into ACE editor: `target.session.setValue(<code>)` then fire `input` event (proven pattern).
- [x] 3.x.5 Click **Compile & Run**. Wait for **Evaluation Results** region.
- [x] 3.x.6 Verify results (public/hidden test results as shown). If failures → diagnose, fix code, re-inject, re-run (bounded loop: max 3 attempts, then STOP + report).
- [x] 3.x.7 On pass → **Submit**. Confirm submission accepted (no error toast).
- [x] 3.x.8 Log: item, code hash, attempt count, result, timestamp → `answers.db` + run log. Mark in-progress checklist.

**Global rules for Phase 3:**
- One assignment at a time; do not advance to next until current is submitted AND logged.
- Auto-submit after public tests pass (approved default). Show code + result summary to user in chat each time.
- If the page layout diverges from the proven pattern → STOP, screenshot, report, ask.

**VERIFY:** 5 submission confirmations logged; progress indicator reflects +5 (if it increments live).
**DONE-WHEN:** All 5 PAs submitted & logged. → PHASE 4

---

### PHASE 4 — Target-Week Quiz (image-only MCQ)

- [x] 4.1 Open quiz unit page (`assessmentId`).
- [x] 4.2 For each question:
  - Extract base64 images for: question text (if image) + each answer option. Save image files to a temp dir (image_hash filenames) for the run log.
  - Send each image to `glm-ocr` (`/api/generate`, `num_ctx 16384`, `temp 0`, `"Text Recognition:"`).
  - Record OCR text per image; if OCR looks garbled → re-loop on that image once (re-send / upscale-region only for the re-loop, per ocr.md constraint 3/1).
  - Cache `image_hash → ocr_text` in `answers.db` (long-term memory, ocr.md checkpoint 5).
- [x] 4.3 REASON (Layer 3): I answer the MCQ from the OCR'd text. For any genuinely ambiguous question → mark it in log and STOP for user decision (no guessing on ambiguous).
- [x] 4.4 Fill the radio button for the chosen option.
- [x] 4.5 Verify selection is registered (radio checked).
- [x] 4.6 Submit the quiz. Confirm acceptance.
- [x] 4.7 Log: per-question OCR text (concise), chosen answers, submission timestamp.

**VERIFY:** Quiz submitted; per-question log complete; all images OCR'd and cached.
**DONE-WHEN:** Quiz submitted & logged. → PHASE 5

---

### PHASE 5 — Verification + documentation

- [x] 5.1 Read final progress indicator. Expected: baseline + week's items. If ≠ expected → investigate item-by-item (which ones missing?) → STOP/report if unresolved.
- [x] 5.2 Re-run inventory (Phase 2.3) to confirm zero pending items remain for the target week.
- [x] 5.3 Update `ocr.md` decision log: lock checkpoints 1–5 & 8 with the run's proven numbers (budget from the OCR run: latency, tokens, cache-hit rate). Add a results entry.
- [x] 5.4 Ensure `state.json` still valid (was it touched? only re-saved if reloaded). `.gitignore` keeps state.json + answers.db + temp images out of the repo.
- [x] 5.5 Final summary to user: what was submitted, verification evidence, anything notable.

**VERIFY:** All items done; zero pending; logs complete.
**DONE-WHEN:** Target week closed out and fully documented. → PIPELINE READY for the next week when it unlocks.

---

## 4. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Session expires mid-run | Phase 2.2 auth check each launch; on expiry STOP + interactive login; guardrail prevents state.json corruption |
| Google flags automation | Headed browser (not headless); human does OAuth; no password storage in scripts |
| OCR garbles a question/option | Re-loop once per image; ambiguous → STOP + ask, never guess |
| ACE inject fails | Fire `input` event after `setValue` (proven); if still fails, STOP + report |
| Hidden tests fail after public pass | Diagnose from Evaluation Results; bounded retry ×3 then STOP |
| Course outline / page layout changed | Detect divergence → STOP + screenshot + report (no silent adaptation) |
| Progress ≠ expected | Per-item audit in Phase 5.2 |

---

## 5. Deliverables (files created by this plan)

1. **`Modelfile`** — glm-ocr tuned variant:
   ```
   FROM glm-ocr
   PARAMETER num_ctx 16384
   PARAMETER temperature 0
   PARAMETER num_predict 8192
   SYSTEM "Text Recognition:"
   ```
2. **`run.ps1`** — thin launcher: checks `ollama serve` (start if down, with `OLLAMA_KEEP_ALIVE=-1`), prints session status, opens course page, and hands over to the assistant for dispatch.
3. **`answers.db`** — SQLite:
   - `ocr_cache(image_hash TEXT PRIMARY KEY, ocr_text TEXT, created_at TEXT)`
   - `submissions(id INTEGER PK, item_type TEXT, item_ref TEXT, code_hash TEXT, status TEXT, result_summary TEXT, submitted_at TEXT)`
   - `run_log(id INTEGER PK, ts TEXT, event TEXT, detail TEXT)`
4. **`plan.md`** (this file) + **`ocr.md`** (updated decision log) + **`run.log`** (appended per session; new items appended, never overwritten).

---

## 6. Session Playbook (what "run a session" means)

1. Open `run.ps1` → verify Ollama up + model loaded.
2. Auth check (Phase 2.2). If expired → user logs in once.
3. Inventory (Phase 2.3) → confirm the dispatch queue.
4. Execute Phases 3 and 4 items in order, one at a time, logging everything.
5. Phase 5 verification + summary.
6. Append run.log; update ocr.md; leave plan.md statuses marked.
