"""Tests for configuration loading and environment interpolation."""

from __future__ import annotations

import os
from pathlib import Path

from src.config import load_config


def test_load_config_reads_loki_url(tmp_path: Path) -> None:
    """Loads the main config fields and expands the GitLab token.

    Args:
        tmp_path: Pytest-provided temporary directory.
    """
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        """
loki:
  url: "http://loki:3100"
  lookback_minutes: 1
  queries:
    - '{job=~"system|windows_events|journald"}'
    - '{container=~".+"}'
gitlab:
  url: "https://gitlab.example.com"
  token: "${GITLAB_TOKEN}"
  group: "example-group"
  patrol_label: "example-patrol"
  stale_days: 3
llm:
  base_url: "http://ollama:11434"
  model: "mistral:7b-instruct-q4_K_M"
  timeout_seconds: 30
  skip_llm_if_level_error: true
  context_window: 32768
  max_log_chars: 400
state:
  db_path: "/data/state.db"
exclude_patterns: []
""",
        encoding="utf-8",
    )
    os.environ["GITLAB_TOKEN"] = "test-token-abc"

    cfg = load_config(str(cfg_file))

    assert cfg.loki.url == "http://loki:3100"
    assert cfg.loki.queries == [
        '{job=~"system|windows_events|journald"}',
        '{container=~".+"}',
    ]
    assert cfg.gitlab.token == "test-token-abc"
    assert cfg.gitlab.stale_days == 3
    assert cfg.llm.context_window == 32768
    assert cfg.llm.max_log_chars == 400


def test_load_config_supports_legacy_loki_query(tmp_path: Path) -> None:
    """Converts the legacy single Loki query field into a list.

    Args:
        tmp_path: Pytest-provided temporary directory.
    """
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        """
loki:
  url: "http://loki:3100"
  lookback_minutes: 1
  query: '{job="system"}'
gitlab:
  url: "https://gitlab.example.com"
  token: "token"
  group: "example-group"
  patrol_label: "example-patrol"
  stale_days: 3
llm:
  base_url: "http://ollama:11434"
  model: "mistral:7b-instruct-q4_K_M"
  timeout_seconds: 30
  skip_llm_if_level_error: true
state:
  db_path: "/data/state.db"
""",
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))

    assert cfg.loki.queries == ['{job="system"}']
    assert cfg.llm.context_window == 32768
    assert cfg.llm.max_log_chars == 400
