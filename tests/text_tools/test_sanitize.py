"""Tests for terminal control-character sanitization."""

from __future__ import annotations

from src.text_tools import sanitize_text


def test_sanitize_text_removes_ansi_sequences() -> None:
    """Removes ANSI color escape sequences from log text."""
    raw = "status \x1b[0;31mFAILED\x1b[0m"
    assert sanitize_text(raw) == "status FAILED"


def test_sanitize_text_removes_control_characters() -> None:
    """Removes disallowed control bytes while preserving tabs and newlines."""
    raw = "hello\x00\x07 world\nnext\tline"
    assert sanitize_text(raw) == "hello world\nnext\tline"
