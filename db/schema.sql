-- ============================================================
-- NPTEL Course Automation Pipeline — SQLite schema
-- Source of truth. The DB itself (db/answers.db) is git-ignored.
-- ============================================================

-- Long-term OCR memory: image_hash -> extracted text.
-- Keyed by sha256 of the raw image bytes so identical questions
-- never get re-OCR'd.
CREATE TABLE IF NOT EXISTS ocr_cache (
    image_hash TEXT PRIMARY KEY,
    ocr_text   TEXT,
    created_at TEXT
);

-- Every submitted assignment / quiz attempt.
CREATE TABLE IF NOT EXISTS submissions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type      TEXT,            -- 'progassignment' | 'quiz'
    item_ref       TEXT,            -- e.g. 'PA1 (progassignmentId=<id>)' | 'assessmentId=<id>'
    code_hash      TEXT,            -- sha256 (first 16) of code / answer JSON
    status         TEXT,            -- 'submitted'
    result_summary TEXT,            -- e.g. 'Public 1/1, Private 1/1, progress N->N+1'
    submitted_at   TEXT
);

-- Session audit trail.
CREATE TABLE IF NOT EXISTS run_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT,
    event  TEXT,
    detail TEXT
);

-- Convenience indexes
CREATE INDEX IF NOT EXISTS idx_ocr_created ON ocr_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_submissions_ref ON submissions(item_ref);
CREATE INDEX IF NOT EXISTS idx_runlog_ts ON run_log(ts);
