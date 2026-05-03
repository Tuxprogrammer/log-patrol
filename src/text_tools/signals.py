"""Signal extraction helpers used for issue-title generation."""

from __future__ import annotations

import re
from typing import Any

from src.loki_client.models import LogEntry
from src.text_tools.json_tools import parse_message_json, truncate_text

_PATH_RE = re.compile(r"(/[^\s\"']+)")


def _signal_from_json_payload(
    payload: dict[str, Any],
    default_service: str,
) -> tuple[str, str] | None:
    """Return a structured signal and subject from a JSON log payload."""
    event_id = str(payload.get("event_id", ""))
    if event_id == "4625":
        user = str(
            payload.get("targetUserName")
            or payload.get("subjectUserName")
            or "unknown"
        )
        computer = str(payload.get("computer") or payload.get("host") or default_service)
        return "auth-fail", f"4625 on {computer} user={user}"

    method = str(payload.get("method", "")).upper()
    event = str(payload.get("event") or payload.get("path") or "").strip()
    logger_name = str(payload.get("logger") or default_service)
    if method and event.startswith("/"):
        return "auth-event", f"{method} {event} ({logger_name})"
    return None


def _message_signal_cases(lowered: str, message: str) -> tuple[str, str] | None:
    """Return the first matching message-level signal classification."""
    if (
        "cannot set ipv4" in lowered
        or "cannot set ipv6" in lowered
        or "record at cloudflare" in lowered
    ):
        domain_match = re.search(r"updating\s+([^:\s]+)", message, re.IGNORECASE)
        record_type = "AAAA" if "ipv6" in lowered or "'aaaa'" in lowered else "A"
        domain = domain_match.group(1) if domain_match else "dns-record"
        return "dns-update-fail", f"{domain} {record_type} record @Cloudflare"

    if "ssl_accept error" in lowered or "tls handshake error" in lowered:
        peer = re.search(r"from\s+([^:\s\[]+)", message, re.IGNORECASE)
        peer_host = peer.group(1) if peer else "peer"
        if "ssl_accept" in lowered:
            return "tls-error", f"SSL_accept from {peer_host}"
        return "tls-error", f"TLS handshake from {peer_host}"

    keyword_cases = (
        ("timeout", "timeout"),
        ("panic", "panic"),
        ("denied", "auth-denied"),
        ("unauthorized", "auth-denied"),
        ("forbidden", "auth-denied"),
        ("failed", "error"),
        ("error", "error"),
        ("exception", "error"),
    )
    if "http" in lowered and " 5" in lowered:
        return "http-5xx", truncate_text(message, 90)
    for token, signal in keyword_cases:
        if token in lowered:
            return signal, truncate_text(message, 90)
    return None


def signal_and_subject(entry: LogEntry) -> tuple[str, str]:
    """Derive a stable issue signal and subject from one log entry.

    Args:
        entry: Log entry to analyze.

    Returns:
        A stable signal and subject pair for issue title generation.
    """
    message = entry.message.strip()
    payload = parse_message_json(message)
    if payload:
        payload_signal = _signal_from_json_payload(payload, entry.service)
        if payload_signal:
            return payload_signal

    lowered = message.lower()
    message_signal = _message_signal_cases(lowered, message)
    if message_signal:
        return message_signal

    path_match = _PATH_RE.search(message)
    if path_match:
        return "event", path_match.group(1)
    return "event", truncate_text(message, 90)
