"""Score a queued job against the resume + profile and persist the result."""
from __future__ import annotations

from typing import Any

from . import config, db, llm, resume_parser


def score_and_store(job: dict[str, Any]) -> dict[str, Any]:
    """Score one job dict (already in DB) and write the result back.

    Jobs at or above the profile threshold become 'scored' (awaiting your
    decision). Below-threshold jobs are auto-'skipped' so the queue stays clean.
    """
    profile = config.load_profile()
    resume = resume_parser.load_cached()
    result = llm.score_job(job, resume, profile)

    threshold = int(profile.get("match_threshold", 70))
    status = "scored" if result["score"] >= threshold else "skipped"

    return db.update_score(
        job["id"],
        score=result["score"],
        rationale=result["rationale"],
        cover_letter=result["cover_letter"],
        answers=result["answers"],
        status=status,
    )
