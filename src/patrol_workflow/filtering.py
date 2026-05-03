"""Filtering and grouping helpers for patrol workflow processing."""

from __future__ import annotations

import re
from collections import defaultdict

from src.loki_client import LogEntry
from src.text_tools import make_fingerprint


def filter_excluded_entries(
    entries: list[LogEntry],
    patterns: list[str],
) -> tuple[list[LogEntry], int]:
    """Drop entries matching configured exclusion regexes.

    Args:
        entries: Candidate log entries to filter.
        patterns: Case-insensitive regex patterns to exclude.

    Returns:
        The kept entries and the number of dropped entries.

    Raises:
        re.error: If any exclusion pattern is invalid.
    """
    if not patterns:
        return entries, 0
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    kept: list[LogEntry] = []
    dropped = 0
    for entry in entries:
        label_blob = " ".join(f"{key}={value}" for key, value in entry.stream_labels.items())
        haystack = " ".join([entry.service, entry.message, label_blob])
        if any(rx.search(haystack) for rx in compiled):
            dropped += 1
            continue
        kept.append(entry)
    return kept, dropped


def group_entries_by_fingerprint(entries: list[LogEntry]) -> dict[str, list[LogEntry]]:
    """Group entries by their normalized fingerprint.

    Args:
        entries: Error entries to group into issue buckets.

    Returns:
        A mapping of fingerprint to the entries sharing that fingerprint.
    """
    by_fingerprint: dict[str, list[LogEntry]] = defaultdict(list)
    for entry in entries:
        fingerprint = make_fingerprint(entry.service, entry.message)
        by_fingerprint[fingerprint].append(entry)
    return by_fingerprint
