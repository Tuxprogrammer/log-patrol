"""Tests for issue title host normalization helpers."""

from __future__ import annotations

from src.loki_client import LogEntry
from src.text_tools.titles import _issue_host, _normalize_host, format_issue_title


def test_normalize_host_and_issue_host_prefer_fqdn_sources() -> None:
    """Normalizes bracket and port formats and prefers FQDN labels over service names."""
    assert _normalize_host("[fe80::1]:9100") == "fe80::1"
    assert _normalize_host("host.example.test:9100") == "host.example.test"

    by_label = LogEntry({"host": "host.example.test:9100"}, 1, "msg")
    by_service = LogEntry({}, 2, "msg")
    by_service.stream_labels["job"] = "service"
    by_message = LogEntry({"job": "svc"}, 3, "failed on mail.example.test during sync")

    assert _issue_host(by_label) == "host.example.test"
    assert _issue_host(LogEntry({"job": "store.example.test"}, 4, "msg")) == "store.example.test"
    assert _issue_host(by_message) == "mail.example.test"
    assert _issue_host(by_service) == "service"


def test_format_issue_title_caps_title_length() -> None:
    """Builds a stable title and caps it to GitLab's length limit."""
    long_host = f"{'a' * 240}.com"
    entry = LogEntry({"job": long_host}, 1, "x" * 400)

    title = format_issue_title(entry, "abcdef0123456789")

    assert len(title) == 255
