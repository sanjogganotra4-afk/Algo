"""SQLite persistence for logged jobs.

Single table `jobs`. Statuses:
  new            - just added, not yet scored
  scored         - scored, awaiting your decision (staged approval)
  applied        - you marked it applied
  skipped        - you (or the score threshold) skipped it
  failed         - scoring failed (LLM error, etc.)
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Optional

from . import config

STATUSES = {"new", "scored", "applied", "skipped", "failed"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL DEFAULT '',
    company      TEXT NOT NULL DEFAULT '',
    location     TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    description  TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'manual',
    status       TEXT NOT NULL DEFAULT 'new',
    score        INTEGER,
    rationale    TEXT NOT NULL DEFAULT '',
    cover_letter TEXT NOT NULL DEFAULT '',
    answers_json TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
"""


def _connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["answers"] = json.loads(d.pop("answers_json") or "{}")
    except json.JSONDecodeError:
        d["answers"] = {}
    return d


def add_job(
    *,
    title: str = "",
    company: str = "",
    location: str = "",
    url: str = "",
    description: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    now = time.time()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO jobs (title, company, location, url, description, source,
                                 status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
            (title, company, location, url, description, source, now, now),
        )
        job_id = cur.lastrowid
    return get_job(job_id)  # type: ignore[return-value]


def get_job(job_id: int) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_jobs(status: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
    with _connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def next_unscored() -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'new' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_score(job_id: int, score: int, rationale: str, cover_letter: str,
                 answers: dict[str, Any], status: str = "scored") -> Optional[dict[str, Any]]:
    with _connect() as conn:
        conn.execute(
            """UPDATE jobs SET score = ?, rationale = ?, cover_letter = ?,
                               answers_json = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (int(score), rationale, cover_letter, json.dumps(answers),
             status, time.time(), job_id),
        )
    return get_job(job_id)


def set_status(job_id: int, status: str) -> Optional[dict[str, Any]]:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, time.time(), job_id),
        )
    return get_job(job_id)


def delete_job(job_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def stats() -> dict[str, Any]:
    day_ago = time.time() - 86400
    week_ago = time.time() - 7 * 86400
    with _connect() as conn:
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status")
        }
        applied_today = conn.execute(
            "SELECT COUNT(*) n FROM jobs WHERE status='applied' AND updated_at >= ?",
            (day_ago,),
        ).fetchone()["n"]
        applied_week = conn.execute(
            "SELECT COUNT(*) n FROM jobs WHERE status='applied' AND updated_at >= ?",
            (week_ago,),
        ).fetchone()["n"]
        avg_row = conn.execute(
            "SELECT AVG(score) a FROM jobs WHERE score IS NOT NULL"
        ).fetchone()
        total = conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
    return {
        "total": total,
        "by_status": by_status,
        "applied_today": applied_today,
        "applied_week": applied_week,
        "avg_score": round(avg_row["a"], 1) if avg_row["a"] is not None else None,
    }
