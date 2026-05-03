"""Tests for JSON parsing and message display helpers."""

from __future__ import annotations

from src.loki_client import LogEntry
from src.text_tools.json_tools import extract_display_message, parse_message_json, truncate_text


def test_truncate_text_and_parse_message_json() -> None:
    """Keeps short text, truncates long text, and parses only JSON objects."""
    assert truncate_text("short", 10) == "short"
    assert truncate_text("1234567890", 7) == "1234..."
    assert parse_message_json("not json") is None
    assert parse_message_json("[1, 2, 3]") is None
    assert parse_message_json('{"message": "ok"}') == {"message": "ok"}


def test_extract_display_message_prefers_payload_fields_or_pretty_json() -> None:
    """Extracts human-friendly message fields and falls back to pretty JSON."""
    plain = LogEntry({"job": "api"}, 1, "plain text")
    msg_field = LogEntry({"job": "api"}, 2, '{"msg": "  trimmed text  ", "code": 500}')
    fallback = LogEntry({"job": "api"}, 3, '{"code": 500, "request_id": "abc"}')

    assert extract_display_message(plain) == "plain text"
    assert extract_display_message(msg_field) == "trimmed text"
    assert '"code": 500' in extract_display_message(fallback)
