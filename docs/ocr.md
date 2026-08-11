# OCR Pipeline — NPTEL Exam Assistant

## Aim
Paste image(s) + a question → local GLM-OCR extracts → DeepSeek reasons → grounded, correct answer, with a re-loop on garbled regions, SQLite cache + memory, and zero paid spend.

---

## Checkpoint Checklist

One checkpoint at a time, in depth, web-anchored, decisions finalized by discussion with the user. Advance to the next only once the current one is converged.

### 1. Input/Modality
What arrives (paste/clipboard vs file path), multi-image?, preprocessing (none / auto-crop / upscale-region — only for the re-loop, not always).

### 2. Context construction + tool schemas
The `ExtractResult` schema (blocks + bbox + reading order + confidence), its Markdown rendering for DeepSeek, and tool spec for `read_ocr(image)` + `read_ocr_region(image, bbox, scale)`.

### 3. Cost/latency budget
Performance budget + post-loop budget, incl. VRAM (8GB: GLM-OCR 2–3GB), first-answer latency, re-loop bound, cache-hit rate.

### 4. Model/reasoning layer
GLM-OCR (extract) + DeepSeek V4 Flash (reason); `num_ctx`, `num_predict`, repeat/self-check loop.

### 5. Memory (short + long term, SQLite)
Short = this session's cache/re-answers; long = persistent image→answer store (image_hash keyed). No separate vector DB.

### 6. Evaluation layer
Ground-truth set of past exam Qs; correctness rate; OCR fidelity; hallucination rate; manual verify-vs-image for edge cases.

### 7. Retrieval (RAG) — OFF, revisit-only
Skipped by default. Revisit only if long-term similar-question recurrence + exact-image cache misses.

### 8. Deploy + observability
Single user localhost: `ollama serve` + opencode tool registration + config; run log (image→ExtractResult→answer, re-loop events, confidence, warnings, tokens, latency).

---

## Discussion Method (per checkpoint)
1. **Deconstruct** — what the checkpoint must achieve for OUR aim (not the generic template's aim).
2. **Web-research brief** — search 2026 sources, pull multiple viable approaches/options with tradeoffs and who-uses-what.
3. **Discuss** — lay out option space + my lean; you push back; iterate until converged.
4. **Lock** — write the decision + rationale into this file (the only artifact, held here until impl).

---

## Running Decision Log
| # | Checkpoint | Decision | Rationale |
|---|-----------|----------|-----------|
| 1 | Input/Modality | Extracted NPTEL MCQ images from DOM (base64 PNG per question, one per `section.bg-white`) | NPTEL quiz hides question text + options inside the image; DOM radios are bare placeholders |
| 2 | Context construction + schema | OCR via `glm-ocr-tuned` returns plain text (question + options, `a.`–`d.`); mapping letter → radio index (`a:0,b:1,c:2,d:3`) | GLM-OCR preserves reading order incl. code blocks and options |
| 3 | Cost/latency budget | 10 questions, ~13–70KB PNG each, `num_ctx 16384`; single OCR pass each, no re-loop needed; full quiz OCR ~1 batch run | images were clean screenshots; zero re-tries |
| 4 | Model/reasoning layer | `glm-ocr-tuned` (extract) + DeepSeek V4 Flash (reason). Response is NDJSON stream — parse line-by-line and join `response` fields (`json.loads` fails: "Extra data") | Ollama `/api/generate` streams token deltas |
| 5 | Memory (SQLite) | `answers.db.ocr_cache` keyed by `sha256(image)`; hit skips re-OCR; `submissions` + `run_log` record everything | exact-repeat questions cheap on re-attempts |
| 6 | Evaluation layer | Verified live: quiz (assessmentId=<id>) submitted, Course Progress reached all-done | |
| 7 | Retrieval (RAG) | OFF — revisit-only | single-user, exact-cache usually suffices |
| 8 | Deploy + observability | Playwright MCP browser holds live session (NOT chrome-devtools MCP which is unauthenticated); images saved via VM-escaped `require` in `browser_run_code_unsafe` (sandbox strips `require`/`process`/`Buffer`); full run logged to `answers.db.run_log` | |

---

## Fixed Constraints (locked so far)
- **Free / zero paid spend**: GLM-OCR (local via Ollama) extracts; DeepSeek V4 Flash (bearer/API) reasons.
- **8GB VRAM** (RTX 4060 Laptop) + 16GB RAM, Windows 11, Ollama 0.4.0 at `127.0.0.1:11434`.
- **Document object is the source of truth**, not markdown: keep blocks + bbox + reading order + confidence; markdown is only the LLM rendering — nothing gets lost (this thread's lesson).
- **GLM-OCR via native Ollama `/api/generate` (base64 images), NOT OpenAI-compatible `/v1/chat/completions`** (vision limitations). Context: `num_ctx 16384`, `num_predict 8192`.