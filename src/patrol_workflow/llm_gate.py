"""LLM gating helpers for patrol workflow processing."""

from __future__ import annotations

import logging
from typing import Protocol

from src.loki_client import LogEntry

log = logging.getLogger("log-patrol.main")


class SupportsClassifyIsError(Protocol):  # pylint: disable=too-few-public-methods
    """Structural contract for LLM classifiers used by the gate."""

    async def classify_is_error(self, service: str, message: str) -> bool:
        """Return whether the log message is actionable."""


async def llm_sentiment_gate(
    entries: list[LogEntry],
    llm: SupportsClassifyIsError,
) -> list[LogEntry]:
    """Apply the final LLM gate to the deterministic classifier output.

    Args:
        entries: Deterministically classified candidate error entries.
        llm: LLM client used for the final yes-or-no filter.

    Returns:
        Entries kept after the LLM sentiment gate.
    """
    if not entries:
        return []
    kept: list[LogEntry] = []
    total = len(entries)
    for idx, entry in enumerate(entries, 1):
        verdict = await llm.classify_is_error(entry.service, entry.message)
        if verdict:
            kept.append(entry)
        if idx % 10 == 0 or idx == total:
            log.info("LLM sentiment progress: %d/%d", idx, total)
    return kept
