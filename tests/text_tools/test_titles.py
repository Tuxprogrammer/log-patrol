"""Tests for patrol issue title formatting."""

from __future__ import annotations

from src.loki_client import LogEntry
from src.text_tools import format_issue_title


def test_title_format_authentik_json_event() -> None:
    """Formats Authentik JSON proxy events into a stable issue title."""
    entry = LogEntry(
        stream_labels={"job": "store.example.test", "host": "store.example.test"},
        timestamp_ns=1,
        message=(
            '{"event":"/outpost.goauthentik.io/auth/nginx",'
            '"host":"app.example.net","level":"info",'
            '"logger":"authentik.outpost.proxyv2.application",'
            '"method":"GET"}'
        ),
    )
    title = format_issue_title(entry, "d7f69896c0db1234")
    assert title == (
        "[store.example.test] [store.example.test] [auth-event] "
        "GET /outpost.goauthentik.io/auth/nginx (authentik.outpost.proxyv2.application) "
        "(fp:d7f69896c0db)"
    )


def test_title_format_dns_update_failure() -> None:
    """Formats DNS update failures into a host and record-specific title."""
    entry = LogEntry(
        stream_labels={"job": "system", "host": "controller.example.test"},
        timestamp_ns=1,
        message=(
            "FAILED: updating service.example.net: Cannot set IPv4 to "
            "203.0.113.16 No 'A' record at Cloudflare"
        ),
    )
    title = format_issue_title(entry, "5cfa93e5a3e81234")
    assert title == (
        "[controller.example.test] [system] [dns-update-fail] "
        "service.example.net A record @Cloudflare (fp:5cfa93e5a3e8)"
    )


def test_title_format_ssl_accept_error() -> None:
    """Formats SMTP TLS accept failures into a peer-specific title."""
    entry = LogEntry(
        stream_labels={"job": "mail.example.test"},
        timestamp_ns=1,
        message=(
            "2026-05-02T21:37:27.308654+00:00 mail postfix/submissions/smtpd[2223]: "
            "SSL_accept error from relay.example.test[203.0.113.10]: lost connection"
        ),
    )
    title = format_issue_title(entry, "5ed76b8d20df1234")
    assert title == (
        "[mail.example.test] [mail.example.test] [tls-error] "
        "SSL_accept from relay.example.test (fp:5ed76b8d20df)"
    )
