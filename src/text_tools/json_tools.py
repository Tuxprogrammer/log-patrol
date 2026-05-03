"""JSON parsing and display helpers for patrol log text."""

from __future__ import annotations

import json
from typing import Any

from src.loki_client.models import LogEntry


def truncate_text(text: str, max_len: int = 180) -> str:
    """Trim text to a stable maximum width for titles and tables.

    Args:
        text: Text to shorten.
        max_len: Maximum allowed output length.

    Returns:
        The original text if already short enough, else an ellipsized string.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def parse_message_json(message: str) -> dict[str, Any] | None:
    """Return a parsed JSON object when the log message contains one.

    Args:
        message: Raw log message text.

    Returns:
        The parsed JSON object when the message is a JSON object, else `None`.
    """
    msg = message.strip()
    if not (msg.startswith("{") and msg.endswith("}")):
        return None
    try:
        payload = json.loads(msg)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def extract_display_message(entry: LogEntry) -> str:
    """Return the most human-readable message text for a sample entry.

    Args:
        entry: Log entry to render for the issue body.

    Returns:
        A readable message string or pretty-printed JSON fallback.
    """
    payload = parse_message_json(entry.message)
    if not payload:
        return entry.message

    for key in ("message", "msg", "log", "event_message", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return json.dumps(payload, indent=2, sort_keys=True)
