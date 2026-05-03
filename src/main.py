"""Main patrol workflow for classifying Loki logs and managing GitLab issues."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from src.config import load_config
from src.db import StateStore
from src.issue_manager import IssueManager, close_stale_issues
from src.llm_client import LLMClient
from src.log_classifier import classify_entries
from src.loki_client import fetch_logs
from src.patrol_workflow import (
    filter_excluded_entries,
    group_entries_by_fingerprint,
    llm_sentiment_gate,
    process_fingerprint_groups,
)
from src.text_tools import format_issue_title as _format_issue_title

log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.WARNING)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

# Third-party network stacks are extremely chatty at DEBUG/INFO; keep them quiet.
for noisy in ("httpx", "httpcore", "anyio", "drain3", "drain3.template_miner"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

log = logging.getLogger("log-patrol.main")

def _print_progress(done: int, total: int) -> None:
    """Emit patrol progress logs at coarse percentage milestones.

    Args:
        done: Number of entries processed so far.
        total: Total entries in the current batch.
    """
    if total <= 0:
        return
    percent = int((done / total) * 100)
    log.info("Log patrol progress: %d%% (%d/%d logs analyzed)", percent, done, total)


async def run_once(config_path: str = "config.yml") -> dict[str, int]:
    """Run one full patrol cycle and return a summary of issue actions.

    Args:
        config_path: Path to the Log Patrol YAML configuration file.

    Returns:
        Counts of detected errors and issue create, update, and close actions.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        KeyError: If required configuration keys are missing.
        TypeError: If the configuration structure is invalid.
        yaml.YAMLError: If the configuration file cannot be parsed.
        httpx.HTTPError: If a Loki or GitLab API request fails.
        ValueError: If GitLab configuration is invalid.
        re.error: If an exclusion pattern is invalid.
    """
    log.info("=== log-patrol run starting ===")
    log.info("Loading config from %s", config_path)
    cfg = load_config(config_path)
    log.debug(
        "Config: loki=%s lookback=%sm queries=%s",
        cfg.loki.url,
        cfg.loki.lookback_minutes,
        cfg.loki.queries,
    )
    log.debug(
        "Config: llm=%s model=%s timeout=%ss",
        cfg.llm.base_url,
        cfg.llm.model,
        cfg.llm.timeout_seconds,
    )
    log.debug(
        "Config: gitlab=%s group=%s stale_days=%s",
        cfg.gitlab.url,
        cfg.gitlab.group,
        cfg.gitlab.stale_days,
    )

    state = StateStore(cfg.state.db_path)
    log.debug("StateStore opened at %s", cfg.state.db_path)
    llm = LLMClient(cfg.llm)
    issues = IssueManager(cfg.gitlab)

    log.info(
        "Fetching logs from Loki (%s, lookback=%dm)...",
        cfg.loki.url,
        cfg.loki.lookback_minutes,
    )
    entries = await fetch_logs(cfg.loki)
    log.info("Loki fetch complete: %d raw log entries", len(entries))
    entries, dropped = filter_excluded_entries(entries, cfg.exclude_patterns)
    if dropped > 0:
        log.info(
            "Excluded %d entries using exclude_patterns=%s",
            dropped,
            cfg.exclude_patterns,
        )

    log.info("Classifying %d entries (template-first detector)...", len(entries))
    error_entries = await classify_entries(entries, progress_callback=_print_progress)
    log.info(
        "Template classification complete: %d entries classified as errors",
        len(error_entries),
    )

    log.info(
        "Running LLM sentiment gate for %d classified errors...",
        len(error_entries),
    )
    llm_gated_entries = await llm_sentiment_gate(error_entries, llm)
    log.info(
        "LLM sentiment gate kept %d/%d entries",
        len(llm_gated_entries),
        len(error_entries),
    )
    error_entries = llm_gated_entries

    by_fingerprint = group_entries_by_fingerprint(error_entries)
    log.info("Grouped into %d fingerprint buckets", len(by_fingerprint))
    created, updated = await process_fingerprint_groups(
        by_fingerprint,
        state=state,
        issues=issues,
        patrol_label=cfg.gitlab.patrol_label,
    )

    log.info(
        "Checking for stale issues to close (stale_days=%d)...",
        cfg.gitlab.stale_days,
    )
    closed = await close_stale_issues(issues, state, cfg.gitlab.stale_days)
    log.info("Stale issues closed: %d", len(closed))

    result = {
        "errors": len(error_entries),
        "created": created,
        "updated": updated,
        "closed": len(closed),
    }
    log.info(
        (
            "=== log-patrol run complete: %d errors found, %d issues created, "
            "%d updated, %d closed ==="
        ),
        result["errors"],
        result["created"],
        result["updated"],
        result["closed"],
    )
    return result


def main() -> None:
    """Run the patrol loop entry point once in the current process."""
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
