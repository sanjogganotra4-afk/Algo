"""LLM helper: resume structuring, job match scoring, cover-letter drafting.

Uses the Anthropic SDK when ANTHROPIC_API_KEY is set. Falls back to a local
keyword-overlap heuristic when there's no key or the SDK/network is unavailable,
so the copilot always runs — just with rougher scores and template letters.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from . import config

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "this", "that", "from", "job", "role", "work", "team", "must", "who", "all",
    "can", "not", "but", "per", "was", "has", "its", "into", "any", "out",
    "a", "an", "of", "to", "in", "on", "as", "at", "or", "is", "be", "we",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.]{2,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _client() -> Optional[Any]:
    settings = config.llm_settings()
    if not settings["anthropic_api_key"]:
        return None
    try:
        import anthropic
    except Exception:
        return None
    try:
        return anthropic.Anthropic(api_key=settings["anthropic_api_key"])
    except Exception:
        return None


def _call_json(prompt: str, schema: dict[str, Any], max_tokens: int = 4000) -> Optional[dict[str, Any]]:
    """One-shot structured-output call. Returns None if the LLM is unavailable."""
    client = _client()
    if client is None:
        return None
    model = config.llm_settings()["model"]
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return json.loads(text)
    except Exception:
        return None


# ── Resume structuring ────────────────────────────────────────────────────

_RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "years_experience": {"type": "number"},
        "work_history": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["title", "company", "summary"],
                "additionalProperties": False,
            },
        },
        "education": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["skills", "years_experience", "work_history", "education",
                 "certifications", "summary"],
    "additionalProperties": False,
}


def structure_resume(raw_text: str) -> dict[str, Any]:
    """Turn raw CV text into structured JSON (LLM if available, else heuristic)."""
    prompt = (
        "Extract structured data from this resume. Return skills as concrete "
        "technologies/competencies, estimate total years of professional experience, "
        "summarise each role in one line, and write a 2-sentence professional summary.\n\n"
        f"RESUME:\n{raw_text[:12000]}"
    )
    result = _call_json(prompt, _RESUME_SCHEMA, max_tokens=3000)
    if result is not None:
        result["_source"] = "llm"
        return result

    # Heuristic fallback: pull the most frequent capitalised / techy tokens.
    kws = _keywords(raw_text)
    common_skills = sorted(kws, key=lambda w: raw_text.lower().count(w), reverse=True)[:25]
    return {
        "skills": common_skills,
        "years_experience": 0,
        "work_history": [],
        "education": [],
        "certifications": [],
        "summary": raw_text.strip()[:300],
        "_source": "heuristic",
    }


# ── Job scoring + cover letter ────────────────────────────────────────────

_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "rationale": {"type": "string"},
        "cover_letter": {"type": "string"},
        "answers": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
            },
            "required": ["question", "answer"],
            "additionalProperties": False,
        }},
    },
    "required": ["score", "rationale", "cover_letter", "answers"],
    "additionalProperties": False,
}


def score_job(job: dict[str, Any], resume: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Return {score, rationale, cover_letter, answers}."""
    screening = profile.get("screening_answers", {})
    prompt = (
        "You are helping a candidate decide whether to apply for a job and drafting "
        "materials they will review before submitting themselves.\n\n"
        f"CANDIDATE PROFILE:\n"
        f"- Name: {profile.get('full_name','')}\n"
        f"- Target titles: {', '.join(profile.get('target_titles', []))}\n"
        f"- Keywords: {', '.join(profile.get('keywords', []))}\n"
        f"- Seniority: {profile.get('seniority','')}\n"
        f"- Locations: {', '.join(profile.get('locations', []))}\n"
        f"- Work authorization: {profile.get('work_authorization','')}\n"
        f"- Known screening answers: {json.dumps(screening)}\n\n"
        f"STRUCTURED RESUME:\n{json.dumps(resume)[:6000]}\n\n"
        f"JOB:\nTitle: {job.get('title','')}\nCompany: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description:\n{job.get('description','')[:6000]}\n\n"
        f"Cover-letter style: {profile.get('cover_letter_style','concise and specific')}.\n\n"
        "Return:\n"
        "- score: 0-100 fit between this candidate and this job.\n"
        "- rationale: 2-3 sentences on the strongest matches and biggest gaps.\n"
        "- cover_letter: a tailored draft (150-250 words) the candidate can edit.\n"
        "- answers: drafts for any screening questions visible in the description, "
        "plus the common ones (relocation, visa, start date) using the known answers."
    )
    result = _call_json(prompt, _MATCH_SCHEMA, max_tokens=4000)
    if result is not None:
        answers = {a["question"]: a["answer"] for a in result.get("answers", [])}
        return {
            "score": max(0, min(100, int(result.get("score", 0)))),
            "rationale": result.get("rationale", ""),
            "cover_letter": result.get("cover_letter", ""),
            "answers": answers,
            "source": "llm",
        }

    # Heuristic fallback: keyword overlap between resume/profile and the JD.
    return _heuristic_score(job, resume, profile)


def _heuristic_score(job: dict[str, Any], resume: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    jd = _keywords(job.get("description", "") + " " + job.get("title", ""))
    cand = _keywords(" ".join(resume.get("skills", []))
                     + " " + " ".join(profile.get("keywords", []))
                     + " " + " ".join(profile.get("target_titles", [])))
    if not jd:
        score = 0
        overlap: set[str] = set()
    else:
        overlap = jd & cand
        score = min(100, round(100 * len(overlap) / max(8, len(jd) * 0.35)))
    matched = ", ".join(sorted(overlap)[:8]) or "no strong keyword overlap"
    name = profile.get("full_name", "").split(" ")[0] or "there"
    company = job.get("company", "the team")
    title = job.get("title", "this role")
    return {
        "score": score,
        "rationale": (f"Keyword-overlap estimate (no LLM key set). "
                      f"Matched signals: {matched}. Add an ANTHROPIC_API_KEY for a real assessment."),
        "cover_letter": (
            f"Dear {company} team,\n\n"
            f"I'm excited to apply for the {title} role. My background lines up with "
            f"several of your requirements ({matched}), and I'd welcome the chance to "
            f"contribute. I've attached my CV and would be glad to discuss further.\n\n"
            f"Best regards,\n{profile.get('full_name','') or name}"
        ),
        "answers": {
            "Are you willing to relocate?": profile.get("screening_answers", {}).get("willing_to_relocate", ""),
            "Do you require visa sponsorship?": profile.get("screening_answers", {}).get("requires_visa_sponsorship", ""),
            "Earliest start date?": profile.get("screening_answers", {}).get("earliest_start_date", ""),
        },
        "source": "heuristic",
    }


def available() -> bool:
    return _client() is not None
