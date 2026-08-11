#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR images using a local Ollama vision model, with SQLite caching.

Usage:
    python scripts/ocr.py <image_dir> [--pattern q*.png] [--no-cache]
    python scripts/ocr.py .playwright-mcp/quiz        # OCR all images in a dir

Reads .env for OLLAMA_HOST / OLLAMA_MODEL / GLM_OCR_CTX / GLM_OCR_PREDICT / DB_PATH.

Notes:
  - The Ollama /api/generate response is an NDJSON stream (one JSON object per
    line). We parse line-by-line and join the `response` fields. A plain
    `json.loads` on the whole body fails with "Extra data" — do NOT change this.
  - Caches by sha256 of raw image bytes in ocr_cache so repeat questions cost 0.
"""

import base64
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request


def load_env(path: str = ".env") -> dict:
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def ocr_image(b64_image: str, cfg: dict) -> str:
    """Send one base64 image to the tuned OCR model. Returns text."""
    body = json.dumps({
        "model": cfg["OLLAMA_MODEL"],
        "images": [b64_image],
        "prompt": "Text Recognition:",
        "options": {
            "num_ctx": int(cfg.get("GLM_OCR_CTX", 16384)),
            "num_predict": int(cfg.get("GLM_OCR_PREDICT", 8192)),
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["OLLAMA_HOST"] + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = []
        for line in resp.read().decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("response"):
                out.append(obj["response"])
            if obj.get("done"):
                break
        return "".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.stderr.write(__doc__)
        sys.exit(2)

    image_dir = args[0]
    pattern = args[1] if len(args) > 1 else "*.png"
    use_cache = "--no-cache" not in flags

    env = load_env()
    cfg = {
        "OLLAMA_HOST": env.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        "OLLAMA_MODEL": env.get("OLLAMA_MODEL", "glm-ocr-tuned"),
        "GLM_OCR_CTX": env.get("GLM_OCR_CTX", "16384"),
        "GLM_OCR_PREDICT": env.get("GLM_OCR_PREDICT", "8192"),
        "DB_PATH": env.get("DB_PATH", "db/answers.db"),
    }

    conn = sqlite3.connect(cfg["DB_PATH"])
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ocr_cache "
        "(image_hash TEXT PRIMARY KEY, ocr_text TEXT, created_at TEXT)"
    )

    import fnmatch

    files = sorted(
        f for f in os.listdir(image_dir)
        if fnmatch.fnmatch(f, pattern) and os.path.isfile(os.path.join(image_dir, f))
    )
    if not files:
        sys.stderr.write(f"No files match '{pattern}' in {image_dir}\n")
        sys.exit(1)

    results = {}
    for name in files:
        path = os.path.join(image_dir, name)
        raw = open(path, "rb").read()
        h = hashlib.sha256(raw).hexdigest()

        row = None
        if use_cache:
            row = conn.execute(
                "SELECT ocr_text FROM ocr_cache WHERE image_hash=?", (h,)
            ).fetchone()
        if row:
            text = row[0]
            src = "CACHE"
        else:
            text = ocr_image(base64.b64encode(raw).decode(), cfg)
            if use_cache:
                conn.execute(
                    "INSERT OR REPLACE INTO ocr_cache (image_hash, ocr_text, created_at) "
                    "VALUES (?,?,datetime('now'))",
                    (h, text),
                )
                conn.commit()
            src = "OCR"

        results[name] = text
        print(f"===== {name} [{src}] =====")
        print(text)
        print()

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
