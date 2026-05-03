"""Issue-title formatting helpers for patrol log entries."""

from __future__ import annotations

import re

from src.loki_client.models import LogEntry
from src.text_tools.signals import signal_and_subject

_FQDN_RE = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})\b")


def _normalize_host(value: str) -> str:
    """Normalize host-like values extracted from labels or log text."""
    host = value.strip()
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    if host.count(":") == 1 and not host.startswith("http"):
        left, right = host.rsplit(":", 1)
        if right.isdigit():
            host = left
    return host


def _issue_host(entry: LogEntry) -> str:
    """Return the best host label or host-like token for an issue title."""
    for key in ("host", "instance", "node", "job"):
        value = entry.stream_labels.get(key)
        if not value:
            continue
        normalized = _normalize_host(str(value))
        if "." in normalized:
            return normalized

    service = _normalize_host(entry.service)
    if "." in service:
        return service

    match = _FQDN_RE.search(entry.message)
    if match:
        return match.group(1)
    return service


def format_issue_title(entry: LogEntry, fingerprint: str) -> str:
    """Build the GitLab issue title for one fingerprinted log entry.

    Args:
        entry: Representative log entry for the fingerprint group.
        fingerprint: Stable fingerprint for the grouped log entries.

    Returns:
        A GitLab-safe issue title capped to 255 characters.
    """
    host = _issue_host(entry)
    signal, subject = signal_and_subject(entry)
    service = entry.service
    title = f"[{host}] [{service}] [{signal}] {subject} (fp:{fingerprint[:12]})"
    return title[:255]
