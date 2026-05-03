"""Tests for LLM prompt building and fallback behavior."""

from __future__ import annotations

from typing import cast

import httpx
import pytest

from src.config import LLMConfig
from src.llm_client import LLMClient
from tests.http_stubs import ResponseStub


class _LLMClientStub:
    """Simulate the async Ollama client used by the LLM tests.

    The stub can either return a fixed generation payload or raise a configured
    exception, which lets the tests exercise both successful classification and
    endpoint-failure fallback behavior deterministically.

    Attributes:
        payload: JSON payload returned by the stubbed response.
        exc: Optional exception raised instead of returning a payload.
        last_json: Most recent JSON body submitted through `post()`.
    """

    def __init__(self, payload: object = None, exc: Exception | None = None) -> None:
        """Store the desired response payload or exception."""
        self.payload = payload
        self.exc = exc
        self.last_json: dict[str, object] | None = None

    async def __aenter__(self) -> _LLMClientStub:
        """Enter the async client context.

        Returns:
            This stub instance.
        """
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        """Exit the async client context without suppression.

        Args:
            exc_type: Exception type raised in the context, if any.
            exc: Exception instance raised in the context, if any.
            tb: Traceback object for the raised exception, if any.

        Returns:
            `False` so any exception propagates.
        """
        return False

    async def post(self, _url: str, json: dict[str, object] | None = None) -> ResponseStub:
        """Return a canned LLM generation response."""
        self.last_json = json
        if self.exc:
            raise self.exc
        return ResponseStub(self.payload)


async def test_classify_is_error_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treats a leading yes response from the LLM as actionable."""
    client = _LLMClientStub(payload={"response": "yes"})
    monkeypatch.setattr("src.llm_client.client.httpx.AsyncClient", lambda **kwargs: client)
    llm = LLMClient(
        LLMConfig(
            base_url="http://ollama:11434",
            model="mistral",
            timeout_seconds=10,
            skip_llm_if_level_error=True,
        )
    )
    assert await llm.classify_is_error("svc", "message") is True
    payload = cast(dict[str, object], client.last_json)
    assert "Answer only with \"yes\" or \"no\"" in cast(str, payload["prompt"])
    assert cast(dict[str, object], payload["options"])["num_ctx"] == 32768


async def test_classify_timeout_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults to not-error when the LLM endpoint times out."""
    client = _LLMClientStub(exc=httpx.ConnectTimeout("timeout"))
    monkeypatch.setattr("src.llm_client.client.httpx.AsyncClient", lambda **kwargs: client)
    llm = LLMClient(
        LLMConfig(
            base_url="http://ollama:11434",
            model="mistral",
            timeout_seconds=10,
            skip_llm_if_level_error=True,
        )
    )
    assert await llm.classify_is_error("svc", "message") is False


def test_clean_log_text_removes_stopwords_and_truncates() -> None:
    """Drops stop words and truncates long log lines before prompting."""
    llm = LLMClient(
        LLMConfig(
            base_url="http://ollama:11434",
            model="mistral",
            timeout_seconds=10,
            skip_llm_if_level_error=True,
            max_log_chars=24,
        )
    )
    cleaned = llm.clean_log_text("the process was killed by the kernel and the system was down")
    assert cleaned == "process killed kernel..."
