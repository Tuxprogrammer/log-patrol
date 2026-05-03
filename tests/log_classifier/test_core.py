"""Tests for the deterministic-first log classifier."""

from __future__ import annotations

from src.log_classifier import _progress_marks, classify_entries
from src.loki_client import LogEntry


async def test_classifier_keeps_explicit_error_levels() -> None:
    """Keeps entries whose labels explicitly mark them as errors."""
    entries = [
        LogEntry({"job": "svc", "level": "error"}, 1, "boom"),
        LogEntry({"job": "svc", "level": "info"}, 2, "ok"),
    ]
    result = await classify_entries(entries)
    assert [entry.message for entry in result] == ["boom"]


async def test_classifier_uses_template_rarity_for_ambiguous_error_lines() -> None:
    """Keeps rare ambiguous templates that still look error-like."""
    entries = [
        LogEntry({"job": "svc"}, 1, "worker heartbeat complete"),
        LogEntry({"job": "svc"}, 2, "worker heartbeat complete"),
        LogEntry({"job": "svc"}, 3, "worker heartbeat complete"),
        LogEntry({"job": "svc"}, 4, "request failed for payment gateway"),
    ]
    result = await classify_entries(entries)
    assert [entry.message for entry in result] == ["request failed for payment gateway"]


async def test_classifier_ignores_rare_non_error_templates() -> None:
    """Ignores rare templates that do not contain error-like hints."""
    entries = [
        LogEntry({"job": "svc"}, 1, "session started for user alice"),
        LogEntry({"job": "svc"}, 2, "session started for user bob"),
        LogEntry({"job": "svc"}, 3, "session started for user charlie"),
    ]
    result = await classify_entries(entries)
    assert result == []


def test_progress_marks_emit_percentages() -> None:
    """Emits evenly spaced progress marks for different batch sizes."""
    assert not _progress_marks(0)
    assert _progress_marks(1) == [1]
    assert _progress_marks(10) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert _progress_marks(25) == [3, 5, 8, 10, 13, 15, 18, 20, 23, 25]


async def test_classifier_reports_progress() -> None:
    """Reports each progress milestone for a small batch size."""
    entries = [LogEntry({"job": "svc", "level": "info"}, idx, f"ok {idx}") for idx in range(10)]
    seen: list[tuple[int, int]] = []
    await classify_entries(
        entries,
        progress_callback=lambda done, total: seen.append((done, total)),
    )
    assert seen == [
        (1, 10),
        (2, 10),
        (3, 10),
        (4, 10),
        (5, 10),
        (6, 10),
        (7, 10),
        (8, 10),
        (9, 10),
        (10, 10),
    ]


async def test_classifier_reports_coarse_progress_for_large_runs() -> None:
    """Reports coarse 10 percent progress milestones for larger runs."""
    entries = [LogEntry({"job": "svc", "level": "info"}, idx, f"ok {idx}") for idx in range(25)]
    seen: list[tuple[int, int]] = []
    await classify_entries(
        entries,
        progress_callback=lambda done, total: seen.append((done, total)),
    )
    assert seen == [
        (3, 25),
        (5, 25),
        (8, 25),
        (10, 25),
        (13, 25),
        (15, 25),
        (18, 25),
        (20, 25),
        (23, 25),
        (25, 25),
    ]
