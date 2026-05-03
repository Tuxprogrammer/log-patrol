"""Configuration loading and typed config structures for Log Patrol."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any

import yaml


@dataclass
class LokiConfig:
    """Loki connection and query settings."""

    url: str
    lookback_minutes: int
    queries: list[str] = field(default_factory=lambda: ['{job=~".+"}'])


@dataclass
class GitLabConfig:
    """GitLab API settings for patrol issue management."""

    url: str
    token: str
    group: str
    patrol_label: str
    stale_days: int
    project: str = ""


@dataclass
class LLMConfig:
    """LLM classifier settings used for the final error gate."""

    base_url: str
    model: str
    timeout_seconds: int
    skip_llm_if_level_error: bool
    context_window: int = 32768
    max_log_chars: int = 400
    temperature: float = 0.0


@dataclass
class StateConfig:
    """Persistent state storage settings."""

    db_path: str


@dataclass
class Config:
    """Top-level application configuration."""

    loki: LokiConfig
    gitlab: GitLabConfig
    llm: LLMConfig
    state: StateConfig
    exclude_patterns: list[str] = field(default_factory=list)


def _interpolate_env(value: str) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)


def _interpolate_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _interpolate_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_obj(v) for v in obj]
    if isinstance(obj, str):
        return _interpolate_env(obj)
    return obj


def load_config(path: str = "config.yml") -> Config:
    """Load configuration from YAML and expand environment placeholders.

    Args:
        path: Filesystem path to the YAML configuration file.

    Returns:
        The parsed application configuration with environment variables expanded.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        KeyError: If required configuration keys are missing.
        TypeError: If the YAML structure does not match the expected shape.
        yaml.YAMLError: If the YAML document cannot be parsed.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    raw = _interpolate_obj(raw)
    loki_raw = dict(raw["loki"])
    if "queries" not in loki_raw:
        loki_raw["queries"] = [loki_raw.pop("query", '{job=~".+"}')]

    return Config(
        loki=LokiConfig(**loki_raw),
        gitlab=GitLabConfig(**raw["gitlab"]),
        llm=LLMConfig(**raw["llm"]),
        state=StateConfig(**raw["state"]),
        exclude_patterns=raw.get("exclude_patterns", []),
    )
