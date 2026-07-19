"""Optional Telegram notifications. No-op when unconfigured."""
from __future__ import annotations

from . import config


def send(text: str) -> bool:
    cfg = config.telegram_settings()
    if not cfg["token"] or not cfg["chat_id"]:
        return False
    try:
        import requests

        requests.post(
            f"https://api.telegram.org/bot{cfg['token']}/sendMessage",
            json={"chat_id": cfg["chat_id"], "text": text},
            timeout=10,
        )
        return True
    except Exception:
        return False
