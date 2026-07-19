"""Configuration + paths for the copilot.

Non-secret profile lives in profile.json (editable from the dashboard or the
setup wizard). Secrets live in .env and are read via os.environ.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is a hard dependency, but degrade gracefully
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

# Project root = the folder that contains this package.
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
PROFILE_PATH = ROOT / "profile.json"
RESUME_STRUCTURED_PATH = ROOT / "resume_structured.json"
DB_PATH = DATA_DIR / "applications.db"
KILL_FLAG = ROOT / "KILL_SWITCH.flag"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Load .env once, from the project root.
load_dotenv(ROOT / ".env")

DEFAULT_MODEL = "claude-opus-4-8"

# Sensible defaults so the app runs before the wizard is ever completed.
DEFAULT_PROFILE: dict[str, Any] = {
    "full_name": "",
    "current_title": "",
    "years_experience": None,
    "keywords": [],
    "target_titles": [],
    "locations": ["Frankfurt am Main", "Remote (EU)"],
    "min_salary": None,
    "salary_currency": "EUR",
    "notice_period": "",
    "work_authorization": "",
    "seniority": "mid",
    "industries_include": [],
    "industries_exclude": [],
    "companies_exclude": [],
    "cover_letter_style": "concise, warm, specific",
    "screening_answers": {
        "willing_to_relocate": "",
        "requires_visa_sponsorship": "",
        "earliest_start_date": "",
    },
    # Copilot behaviour
    "match_threshold": 70,
    "cv_path": "",
}


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def llm_settings() -> dict[str, Any]:
    """Everything the LLM module needs, resolved from env at call time."""
    return {
        "anthropic_api_key": _env("ANTHROPIC_API_KEY"),
        "model": _env("JOBCOPILOT_MODEL") or DEFAULT_MODEL,
    }


def server_settings() -> dict[str, Any]:
    return {
        "host": _env("JOBCOPILOT_HOST") or "0.0.0.0",
        "port": int(_env("JOBCOPILOT_PORT") or "8000"),
    }


def telegram_settings() -> dict[str, str]:
    return {
        "token": _env("TELEGRAM_BOT_TOKEN"),
        "chat_id": _env("TELEGRAM_CHAT_ID"),
    }


def load_profile() -> dict[str, Any]:
    """Load profile.json merged over the defaults (so new keys never break)."""
    profile = json.loads(json.dumps(DEFAULT_PROFILE))  # deep copy
    if PROFILE_PATH.exists():
        try:
            saved = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            profile.update({k: v for k, v in saved.items() if v is not None or k in saved})
        except (json.JSONDecodeError, OSError):
            pass
    return profile


def save_profile(profile: dict[str, Any]) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def ensure_profile() -> None:
    """Create profile.json with defaults if it doesn't exist yet.

    Lets the server (and dashboard) run on a fresh machine with no CLI wizard —
    the user fills the profile in from the iPad, or it's auto-filled from the CV.
    """
    if not PROFILE_PATH.exists():
        save_profile(json.loads(json.dumps(DEFAULT_PROFILE)))


def autofill_profile_from_resume(structured: dict[str, Any]) -> dict[str, Any]:
    """Fill empty profile fields from a parsed resume, then save. Never overwrites
    values the user already set."""
    profile = load_profile()

    def _empty(v: Any) -> bool:
        return v in (None, "", [], 0)

    if _empty(profile.get("full_name")) and structured.get("full_name"):
        profile["full_name"] = structured["full_name"]
    if _empty(profile.get("current_title")) and structured.get("current_title"):
        profile["current_title"] = structured["current_title"]
    if _empty(profile.get("years_experience")) and structured.get("years_experience"):
        try:
            profile["years_experience"] = int(structured["years_experience"])
        except (TypeError, ValueError):
            pass
    if not profile.get("keywords") and structured.get("skills"):
        profile["keywords"] = structured["skills"][:15]
    if not profile.get("target_titles"):
        titles = structured.get("suggested_titles") or []
        if not titles and structured.get("current_title"):
            titles = [structured["current_title"]]
        profile["target_titles"] = [t for t in titles if t]
    profile["cv_path"] = structured.get("_cv_path", profile.get("cv_path", ""))

    save_profile(profile)
    return profile


def env_ready() -> bool:
    """True if the copilot has at least a usable config to run (profile exists)."""
    return PROFILE_PATH.exists()
