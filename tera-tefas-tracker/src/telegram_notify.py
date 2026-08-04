"""Minimal Telegram Bot API sender.

Reads the bot token and target chat id from environment variables
(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) — these are injected as GitHub
Actions secrets and must never be hardcoded or logged.
"""
from __future__ import annotations

import os

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000  # Telegram's hard limit is 4096 characters.


def send_message(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = TELEGRAM_API_URL.format(token=token)

    for chunk in _chunk(text, MAX_MESSAGE_LENGTH):
        resp = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        resp.raise_for_status()


def _chunk(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts = []
    while text:
        parts.append(text[:size])
        text = text[size:]
    return parts
