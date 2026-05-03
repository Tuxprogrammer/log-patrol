"""Fingerprint generation helpers for grouping similar log lines."""

from __future__ import annotations

import hashlib
import re


def normalize_message(msg: str) -> str:
    """Normalize volatile values so similar log lines hash to the same key.

    Args:
        msg: Raw log message text.

    Returns:
        The normalized message with volatile values replaced by stable tokens.
    """
    msg = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "<uuid>", msg, flags=re.I)
    msg = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", msg)
    msg = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:.+-]+Z?\b", "<ts>", msg)
    msg = re.sub(r"\b0x[0-9a-f]+\b", "<hex>", msg, flags=re.I)
    msg = re.sub(r"\b\d{4,}\b", "<num>", msg)
    return re.sub(r"\s+", " ", msg).strip().lower()


def make_fingerprint(service: str, message: str) -> str:
    """Build a stable short fingerprint for a service and log message.

    Args:
        service: Service name associated with the log line.
        message: Raw log message text.

    Returns:
        A stable 16-character fingerprint for the normalized log record.
    """
    key = f"{service.lower()}::{normalize_message(message)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
