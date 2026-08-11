#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Log submissions / run-log entries to the SQLite database, or list recent rows.

Usage:
    python scripts/db_log.py submit --type progassignment --ref "PA1 (progassignmentId=<id>)" \
        --hash <code_hash> --status submitted --result "Public 1/1, Private 1/1"
    python scripts/db_log.py log --event PH3-PA1 --detail "Submitted PA1"
    python scripts/db_log.py show [--table submissions|run_log|ocr_cache] [--limit 10]

Reads .env for DB_PATH.
"""

import argparse
import json
import os
import sqlite3
import sys


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


def get_db() -> sqlite3.Connection:
    env = load_env()
    db_path = env.get("DB_PATH", "db/answers.db")
    conn = sqlite3.connect(db_path)
    with open(os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql"),
              encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


def cmd_submit(args):
    conn = get_db()
    conn.execute(
        "INSERT INTO submissions (item_type, item_ref, code_hash, status, result_summary, submitted_at) "
        "VALUES (?,?,?,?,?,datetime('now'))",
        (args.type, args.ref, args.hash, args.status, args.result),
    )
    conn.commit()
    print("Logged submission:", args.ref)
    conn.close()


def cmd_log(args):
    conn = get_db()
    conn.execute(
        "INSERT INTO run_log (ts, event, detail) VALUES (datetime('now'),?,?)",
        (args.event, args.detail),
    )
    conn.commit()
    print("Logged run_log event:", args.event)
    conn.close()


def cmd_show(args):
    table = args.table if args.table in ("submissions", "run_log", "ocr_cache") else "submissions"
    conn = get_db()
    cols = {
        "submissions": "id, item_type, item_ref, status, result_summary, submitted_at",
        "run_log": "id, ts, event, substr(detail,1,120) AS detail",
        "ocr_cache": "image_hash, substr(ocr_text,1,80) AS ocr_text, created_at",
    }[table]
    rows = conn.execute(f"SELECT {cols} FROM {table} ORDER BY id DESC LIMIT ?",
                        (args.limit,)).fetchall()
    for r in rows:
        print(r)
    conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("submit")
    s.add_argument("--type", required=True)
    s.add_argument("--ref", required=True)
    s.add_argument("--hash", default="")
    s.add_argument("--status", default="submitted")
    s.add_argument("--result", default="")
    s.set_defaults(func=cmd_submit)

    l = sub.add_parser("log")
    l.add_argument("--event", required=True)
    l.add_argument("--detail", default="")
    l.set_defaults(func=cmd_log)

    sh = sub.add_parser("show")
    sh.add_argument("--table", choices=["submissions", "run_log", "ocr_cache"])
    sh.add_argument("--limit", type=int, default=10)
    sh.set_defaults(func=cmd_show)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
