"""Text cleanup helpers for removing terminal control bytes from logs."""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_CTRL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")


def sanitize_text(text: str) -> str:
    """Strip ANSI escape sequences and non-printable control bytes from text.

    Args:
        text: Raw text that may contain terminal control bytes.

    Returns:
        Sanitized text with ANSI sequences and control bytes removed.
    """
    cleaned = _ANSI_RE.sub("", text)
    cleaned = _CTRL_RE.sub("", cleaned)
    return cleaned
