"""Tests for fingerprint normalization and hashing behavior."""

from __future__ import annotations

from src.text_tools import make_fingerprint


def test_fingerprint_same_for_similar_message() -> None:
    """Hashes similar messages with volatile values to the same fingerprint."""
    msg1 = "Request failed for id 12345 uuid 123e4567-e89b-12d3-a456-426614174000"
    msg2 = "Request failed for id 67890 uuid 123e4567-e89b-12d3-a456-426614174999"
    assert make_fingerprint("svc", msg1) == make_fingerprint("svc", msg2)


def test_fingerprint_diff_for_different_service() -> None:
    """Keeps fingerprints distinct across different services."""
    msg = "Database timeout id 12345"
    assert make_fingerprint("api", msg) != make_fingerprint("worker", msg)
