"""Tests for issue body rendering helpers."""

from __future__ import annotations

from src.issue_manager.docs import _build_metadata, _escape_md, build_issue_body, build_run_section
from src.loki_client import LogEntry


def test_escape_md_and_build_metadata_for_plain_text() -> None:
    """Escapes markdown table delimiters and returns basic metadata for plain text."""
    entry = LogEntry({"job": "api", "host": "node1"}, 1, "line one|two\nline three")

    assert _escape_md(entry.message) == "line one\\|two line three"
    assert _build_metadata(entry) == {
        "service": "api",
        "timestamp_ns": 1,
        "stream_labels": {"job": "api", "host": "node1"},
    }


def test_build_metadata_and_run_section_for_json_logs() -> None:
    """Includes redacted JSON metadata and display messages in the run section."""
    sample = LogEntry(
        {"job": "api", "host": "node1"},
        1,
        '{"message":"top line","request_id":"abc","status":500}',
    )
    extra = LogEntry(
        {"job": "api", "host": "node1"},
        2,
        '{"description":"second line","request_id":"xyz"}',
    )

    metadata = _build_metadata(sample)
    section = build_run_section("abcdef0123456789", sample, [sample, extra], 3)

    assert metadata["fields"] == {"request_id": "abc", "status": 500}
    assert "### Patrol Run 3" in section
    assert "top line" in section
    assert "second line" in section
    assert '"request_id": "abc"' in section


def test_build_issue_body_wraps_run_section() -> None:
    """Prepends the issue summary header ahead of the first patrol run section."""
    entry = LogEntry({"job": "api"}, 1, "plain text")

    body = build_issue_body("abcdef0123456789", entry, [entry], 1)

    assert body.startswith("## Log Patrol - `api`")
    assert "### Patrol Run 1" in body
