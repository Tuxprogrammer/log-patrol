"""Log-text cleaning helpers for LLM classification prompts."""

from __future__ import annotations

import re

from stop_words import get_stop_words

STOPWORDS = set(get_stop_words("en"))
SPACE_RE = re.compile(r"\s+")


def clean_log_text(message: str, max_log_chars: int) -> str:
    """Trim noisy stop words and limit log text before prompt submission.

    Args:
        message: Raw log line to condense before model classification.
        max_log_chars: Maximum length allowed in the cleaned prompt text.

    Returns:
        A cleaned and length-limited log string for prompt use.
    """
    collapsed = SPACE_RE.sub(" ", message).strip()
    cleaned_tokens: list[str] = []
    for token in collapsed.split(" "):
        if not token:
            continue
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", token).lower()
        if core and core in STOPWORDS:
            continue
        cleaned_tokens.append(token)

    cleaned = " ".join(cleaned_tokens) or collapsed
    if len(cleaned) > max_log_chars:
        return cleaned[: max_log_chars - 3].rstrip() + "..."
    return cleaned
