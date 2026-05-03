"""Shared async HTTP stubs used across the Log Patrol test suite."""

from __future__ import annotations


class ResponseStub:
    """Provide a minimal HTTP response object for async client tests.

    The stub mirrors the small portion of the `httpx.Response` interface used
    by the test suite so helpers can return deterministic payloads without real
    network traffic or full response construction.

    Attributes:
        _payload: Object returned by `json()` for the stubbed response.
    """

    def __init__(self, payload: object) -> None:
        """Store the JSON payload returned by this stub.

        Args:
            payload: Object returned by the stubbed `json()` method.
        """
        self._payload = payload

    def raise_for_status(self) -> None:
        """Pretend the HTTP response succeeded."""

    def json(self) -> object:
        """Return the configured JSON payload.

        Returns:
            The object configured at stub construction time.
        """
        return self._payload
