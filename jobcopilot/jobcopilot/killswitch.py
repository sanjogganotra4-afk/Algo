"""Kill switch: a flag file that pauses all background LLM processing.

There is no browser automation in this copilot, so there is nothing to abort
mid-action — the switch simply pauses the scoring worker. The desktop KILL
shortcut and the dashboard STOP button both create this file; RESUME removes it.
"""
from __future__ import annotations

from . import config


def is_active() -> bool:
    return config.KILL_FLAG.exists()


def engage() -> None:
    config.KILL_FLAG.write_text("stopped\n", encoding="utf-8")


def release() -> None:
    if config.KILL_FLAG.exists():
        config.KILL_FLAG.unlink()
