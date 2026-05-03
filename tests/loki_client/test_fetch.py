"""Tests for Loki log fetching and service label selection."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from src.config import LokiConfig
from src.loki_client import LogEntry, fetch_logs
from tests.http_stubs import ResponseStub


class _PagedLokiClientStub:
    """Simulate paginated Loki API responses for fetch-log tests.

    The stub returns a pre-seeded sequence of page payloads one request at a
    time, allowing the pagination logic to be tested without a running Loki
    instance or real HTTP traffic.

    Attributes:
        pages: Ordered response payloads returned by successive `get()` calls.
        index: Zero-based pointer to the next page payload to return.
    """

    def __init__(self, pages: Sequence[object]) -> None:
        """Store the ordered Loki pages returned by this client."""
        self.pages = pages
        self.index = 0

    async def __aenter__(self) -> _PagedLokiClientStub:
        """Enter the async client context.

        Returns:
            This stub instance.
        """
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        """Exit the async client context without suppressing exceptions.

        Args:
            exc_type: Exception type raised in the context, if any.
            exc: Exception instance raised in the context, if any.
            tb: Traceback object for the raised exception, if any.

        Returns:
            `False` so any exception propagates.
        """
        return False

    async def get(self, _url: str, params: object = None) -> ResponseStub:
        """Return the next page of Loki results."""
        _ = params
        if self.index >= len(self.pages):
            return ResponseStub({"data": {"result": []}})
        payload = self.pages[self.index]
        self.index += 1
        return ResponseStub(payload)


async def test_loki_fetch_logs_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collects paginated Loki results into one ordered list."""
    page1 = {
        "data": {
            "result": [
                {
                    "stream": {"job": "api"},
                    "values": [["100", "first"], ["101", "second"]],
                }
            ]
        }
    }
    page2 = {"data": {"result": [{"stream": {"job": "api"}, "values": [["102", "third"]]}]}}

    def _factory(**kwargs: object) -> _PagedLokiClientStub:
        _ = kwargs
        return _PagedLokiClientStub([page1, page2])

    monkeypatch.setattr("src.loki_client.fetch.httpx.AsyncClient", _factory)
    cfg = LokiConfig(url="http://loki:3100", lookback_minutes=1)
    entries = await fetch_logs(cfg)
    assert [entry.message for entry in entries] == ["first", "second", "third"]


def test_log_entry_service_priority() -> None:
    """Prefers app labels over lower-priority service-style labels."""
    entry = LogEntry(
        stream_labels={"app": "web", "container_name": "ctr", "host": "node1"},
        timestamp_ns=1,
        message="hello",
    )
    assert entry.service == "web"
