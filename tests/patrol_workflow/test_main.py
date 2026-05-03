"""Tests for the top-level patrol run loop and entry point."""

from __future__ import annotations

from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

import pytest

from src.config import Config, GitLabConfig, LLMConfig, LokiConfig, StateConfig
from src.loki_client import LogEntry
import src.main as main_module


@dataclass
class _StubStateStore:
    """Represent the state store instance created by the main run loop.

    Attributes:
        db_path: Database path received from the configuration.
    """

    db_path: str


class _StubLLM:
    """Capture the LLM config received by the main run loop.

    Attributes:
        cfg: LLM configuration passed to the stub constructor.
    """

    def __init__(self, cfg: LLMConfig) -> None:
        """Store the received configuration.

        Args:
            cfg: LLM configuration from the loaded app config.
        """
        self.cfg = cfg


class _StubIssues:
    """Capture the GitLab config received by the main run loop.

    Attributes:
        cfg: GitLab configuration passed to the stub constructor.
    """

    def __init__(self, cfg: GitLabConfig) -> None:
        """Store the received configuration.

        Args:
            cfg: GitLab configuration from the loaded app config.
        """
        self.cfg = cfg


def _build_config() -> Config:
    """Return a minimal but valid runtime config for patrol tests.

    Returns:
        A complete application config object.
    """
    return Config(
        loki=LokiConfig(url="http://loki:3100", lookback_minutes=5, queries=["{job=~\".+\"}"]),
        gitlab=GitLabConfig(
            url="https://gitlab.example.com",
            token="token",
            group="example-group",
            patrol_label="example-patrol",
            stale_days=7,
            project="example-group/example-project",
        ),
        llm=LLMConfig(
            base_url="http://ollama:11434",
            model="tiny",
            timeout_seconds=10,
            skip_llm_if_level_error=True,
        ),
        state=StateConfig(db_path="state.db"),
        exclude_patterns=["ignore-this"],
    )


async def test_run_once_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs one full patrol cycle and returns the action counts.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    cfg = _build_config()
    raw_entries = [
        LogEntry({"job": "api"}, 1, "ignore-this noise"),
        LogEntry({"job": "api"}, 2, "boom"),
    ]
    filtered_entries = [raw_entries[1]]
    grouped_entries = {"abc123": filtered_entries}

    monkeypatch.setattr(main_module, "load_config", lambda path: cfg)
    monkeypatch.setattr(main_module, "StateStore", _StubStateStore)
    monkeypatch.setattr(main_module, "LLMClient", _StubLLM)
    monkeypatch.setattr(main_module, "IssueManager", _StubIssues)
    async def _fetch(_: object) -> list[LogEntry]:
        return raw_entries

    monkeypatch.setattr(main_module, "fetch_logs", _fetch)

    async def _classify(entries: list[LogEntry], progress_callback: object) -> list[LogEntry]:
        assert entries == filtered_entries
        assert progress_callback is main_module._print_progress
        return entries

    async def _gate(entries: list[LogEntry], llm: _StubLLM) -> list[LogEntry]:
        assert entries == filtered_entries
        assert llm.cfg.model == "tiny"
        return entries

    async def _process(
        by_fingerprint: dict[str, list[LogEntry]],
        *,
        state: _StubStateStore,
        issues: _StubIssues,
        patrol_label: str,
    ) -> tuple[int, int]:
        assert by_fingerprint == grouped_entries
        assert state.db_path == "state.db"
        assert issues.cfg.patrol_label == "example-patrol"
        assert patrol_label == "example-patrol"
        return 2, 3

    async def _close(issues: _StubIssues, state: _StubStateStore, stale_days: int) -> list[int]:
        assert issues.cfg.group == "example-group"
        assert state.db_path == "state.db"
        assert stale_days == 7
        return [10, 11]

    monkeypatch.setattr(
        main_module,
        "filter_excluded_entries",
        lambda entries, patterns: (filtered_entries, 1),
    )
    monkeypatch.setattr(main_module, "classify_entries", _classify)
    monkeypatch.setattr(main_module, "llm_sentiment_gate", _gate)
    monkeypatch.setattr(
        main_module,
        "group_entries_by_fingerprint",
        lambda entries: grouped_entries,
    )
    monkeypatch.setattr(main_module, "process_fingerprint_groups", _process)
    monkeypatch.setattr(main_module, "close_stale_issues", _close)

    result = await main_module.run_once("custom.yml")

    assert result == {"errors": 1, "created": 2, "updated": 3, "closed": 2}


def test_print_progress_ignores_non_positive_total(caplog: pytest.LogCaptureFixture) -> None:
    """Skips logging when the batch size is zero.

    Args:
        caplog: Pytest log capture fixture.
    """
    with caplog.at_level("INFO"):
        main_module._print_progress(1, 0)
    assert not caplog.records


def test_main_runs_async_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delegates the CLI entry point to `asyncio.run`.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    seen: list[Coroutine[Any, Any, dict[str, int]]] = []
    monkeypatch.setattr(
        "src.main.asyncio.run",
        lambda coroutine: seen.append(coroutine),
    )

    main_module.main()

    assert len(seen) == 1
    seen[0].close()
