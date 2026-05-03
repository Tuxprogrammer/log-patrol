"""Top-level deterministic classifier orchestration."""

from __future__ import annotations

import logging
from typing import Callable

from src.loki_client import LogEntry
from src.log_classifier.constants import ERROR_LEVELS, NON_ERROR_LEVELS
from src.log_classifier.progress import progress_marks
from src.log_classifier.templates import (
    build_template_stats,
    find_anomalous_templates,
    mine_templates,
)

log = logging.getLogger("log-patrol.classifier")


def _split_entries_by_level(
    entries: list[LogEntry],
    progress_callback: Callable[[int, int], None] | None,
) -> tuple[list[LogEntry], list[LogEntry]]:
    """Split entries into explicit errors and ambiguous entries."""
    matches: list[LogEntry] = []
    ambiguous: list[LogEntry] = []
    total = len(entries)
    marks = progress_marks(total)
    mark_index = 0
    for idx, entry in enumerate(entries, start=1):
        level = str(entry.stream_labels.get("level", "")).strip().lower()
        if level in ERROR_LEVELS:
            matches.append(entry)
        elif level not in NON_ERROR_LEVELS and entry.message:
            ambiguous.append(entry)
        while mark_index < len(marks) and idx >= marks[mark_index]:
            if progress_callback:
                progress_callback(marks[mark_index], total)
            mark_index += 1
    return matches, ambiguous


async def classify_entries(
    entries: list[LogEntry],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[LogEntry]:
    """Return entries likely to represent actionable errors.

    Args:
        entries: Candidate log entries to evaluate.
        progress_callback: Optional callback invoked at progress milestones.

    Returns:
        Entries that appear likely to represent actionable errors.
    """
    if not entries:
        return []
    matches, ambiguous = _split_entries_by_level(entries, progress_callback)
    log.info(
        "Classifier pre-pass complete: total=%d explicit_error=%d ambiguous=%d",
        len(entries),
        len(matches),
        len(ambiguous),
    )
    if not ambiguous:
        return matches
    template_entries = mine_templates(ambiguous)
    log.info(
        "Template mining complete: ambiguous=%d templates=%d",
        len(ambiguous),
        len(template_entries),
    )
    stats_by_template, all_counts = build_template_stats(template_entries)
    anomalous_templates = find_anomalous_templates(stats_by_template, all_counts)
    if anomalous_templates:
        top_templates = sorted(
            ((template, stats_by_template[template].count) for template in anomalous_templates),
            key=lambda item: item[1],
        )[:10]
        log.debug("Selected anomalous templates (template,count)=%s", top_templates)
    for template in anomalous_templates:
        matches.extend(template_entries[template])
    log.info(
        "Classifier result: anomalous_templates=%d template_matches=%d total_errors=%d",
        len(anomalous_templates),
        sum(len(template_entries[t]) for t in anomalous_templates),
        len(matches),
    )
    return matches
