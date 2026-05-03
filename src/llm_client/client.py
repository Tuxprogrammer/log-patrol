"""Async Ollama client used by the patrol classifier."""

from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse

import httpx

from src.config import LLMConfig
from src.llm_client.cleaning import clean_log_text
from src.llm_client.prompts import build_prompt

log = logging.getLogger("log-patrol.llm")


class LLMClient:
    """Wrap Ollama generation calls used by the patrol classifier.

    The client handles prompt submission, endpoint fallback, and request
    bookkeeping for the final LLM gate that decides whether a candidate log
    line should remain actionable after deterministic filtering.

    Attributes:
        cfg: LLM configuration controlling endpoints, model, and prompt limits.
        _classify_calls: Counter tracking how many classification requests ran.
        _unreachable_endpoints: Base URLs previously observed as unreachable.
    """

    def __init__(self, cfg: LLMConfig):
        """Store client configuration and initialize retry state.

        Args:
            cfg: LLM client settings controlling endpoint, model, and limits.
        """
        self.cfg = cfg
        self._classify_calls = 0
        self._unreachable_endpoints: set[str] = set()

    def _base_urls(self) -> list[str]:
        """Return the primary endpoint plus any local fallback endpoints.

        Returns:
            Ordered base URLs to try for Ollama requests.
        """
        primary = self.cfg.base_url.rstrip("/")
        urls = [primary]
        parsed = urlparse(primary)
        if parsed.hostname == "log-patrol-ollama":
            scheme = parsed.scheme or "http"
            port_suffix = f":{parsed.port}" if parsed.port else ""
            for host in ("localhost", "127.0.0.1"):
                alt = urlunparse(
                    (scheme, f"{host}{port_suffix}", parsed.path, "", "", "")
                ).rstrip("/")
                if alt not in urls:
                    urls.append(alt)
        return urls

    async def _generate(self, prompt: str) -> str:
        """Submit a prompt to the first reachable Ollama endpoint.

        Args:
            prompt: Prompt text to submit to the Ollama generation API.

        Returns:
            The stripped model response text.

        Raises:
            RuntimeError: If no candidate LLM endpoints are available.
            httpx.ConnectError: If every endpoint fails to connect.
            httpx.ConnectTimeout: If every endpoint times out while connecting.
            httpx.HTTPError: If the reachable endpoint returns an HTTP error.
        """
        last_exc: Exception | None = None
        for base_url in self._base_urls():
            log.debug(
                "POST %s/api/generate model=%s prompt_len=%d",
                base_url,
                self.cfg.model,
                len(prompt),
            )
            try:
                async with httpx.AsyncClient(timeout=self.cfg.timeout_seconds) as client:
                    response = await client.post(
                        f"{base_url}/api/generate",
                        json={
                            "model": self.cfg.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"num_ctx": self.cfg.context_window},
                        },
                    )
                response.raise_for_status()
                data = response.json()
                result = str(data.get("response", "")).strip()
                log.debug(
                    "  LLM response: %r (eval_count=%s)",
                    result[:80],
                    data.get("eval_count", "?"),
                )
                return result
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_exc = exc
                if base_url not in self._unreachable_endpoints:
                    log.warning(
                        "LLM endpoint %s unreachable (%s); trying fallback",
                        base_url,
                        exc,
                    )
                    self._unreachable_endpoints.add(base_url)
                else:
                    log.debug("LLM endpoint %s still unreachable; trying fallback", base_url)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No LLM endpoints available")

    def clean_log_text(self, message: str) -> str:
        """Trim noisy stop words and limit log text before prompt submission.

        Args:
            message: Raw log line to condense before model classification.

        Returns:
            A cleaned and length-limited log string for prompt use.
        """
        return clean_log_text(message, self.cfg.max_log_chars)

    async def classify_is_error(self, service: str, message: str) -> bool:
        """Return whether the LLM considers a log line actionable.

        Args:
            service: Service name associated with the log line.
            message: Raw log message to classify.

        Returns:
            `True` when the LLM says the entry is actionable, else `False`.
        """
        self._classify_calls += 1
        log.debug("[classify #%d] service=%s msg=%r", self._classify_calls, service, message[:80])
        cleaned_message = self.clean_log_text(message)
        prompt = build_prompt(service, cleaned_message)
        try:
            answer = (await self._generate(prompt)).lower()
        except (httpx.HTTPError, TimeoutError) as exc:
            log.warning(
                "[classify #%d] LLM call failed (%s), defaulting to not-error",
                self._classify_calls,
                exc,
            )
            return False
        is_error = answer.startswith("yes")
        log.debug("[classify #%d] result=%s (raw=%r)", self._classify_calls, is_error, answer[:20])
        return is_error
