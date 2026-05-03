"""Tests for issue signal extraction heuristics."""

from __future__ import annotations

from src.loki_client import LogEntry
from src.text_tools.signals import signal_and_subject


def test_signal_and_subject_handles_structured_windows_auth_failure() -> None:
    """Builds a stable auth-failure subject from Windows event payloads."""
    entry = LogEntry(
        {"job": "winlog"},
        1,
        '{"event_id":"4625","targetUserName":"alice","computer":"dc01.example.test"}',
    )

    assert signal_and_subject(entry) == ("auth-fail", "4625 on dc01.example.test user=alice")


def test_signal_and_subject_handles_structured_http_auth_event() -> None:
    """Builds an auth-event subject from structured request payloads."""
    entry = LogEntry(
        {"job": "auth"},
        1,
        '{"method":"post","path":"/login","logger":"nginx"}',
    )

    assert signal_and_subject(entry) == ("auth-event", "POST /login (nginx)")


def test_signal_and_subject_handles_textual_signals_and_fallbacks() -> None:
    """Maps textual DNS, TLS, HTTP, path, and generic event messages."""
    dns_entry = LogEntry({"job": "ddns"}, 1, "updating example.com cannot set ipv6 at cloudflare")
    tls_entry = LogEntry({"job": "nginx"}, 2, "SSL_accept error from 203.0.113.5:1234")
    http_entry = LogEntry({"job": "web"}, 3, "HTTP 500 while handling request")
    path_entry = LogEntry({"job": "svc"}, 4, "GET /var/log/app/error.log failed")
    generic_entry = LogEntry({"job": "svc"}, 5, "plain message without keywords")

    assert signal_and_subject(dns_entry) == (
        "dns-update-fail",
        "example.com AAAA record @Cloudflare",
    )
    assert signal_and_subject(tls_entry) == ("tls-error", "SSL_accept from 203.0.113.5")
    assert signal_and_subject(http_entry)[0] == "http-5xx"
    assert signal_and_subject(path_entry) == ("error", "GET /var/log/app/error.log failed")
    assert signal_and_subject(generic_entry) == ("event", "plain message without keywords")
