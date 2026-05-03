"""Template mining helpers for ambiguous log entries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from drain3 import TemplateMiner
from drain3.memory_buffer_persistence import MemoryBufferPersistence
from drain3.template_miner_config import TemplateMinerConfig

from src.loki_client import LogEntry
from src.log_classifier.constants import ERROR_HINT_RE, HTTP_5XX_RE, MAX_RARE_TEMPLATE_COUNT
from src.log_classifier.progress import is_statistical_low_outlier


@dataclass
class TemplateStats:
    """Store count and error-hint metadata for a mined template.

    Attributes:
        count: Number of entries sharing the template.
        has_error_hint: Whether any template entry looks error-like.
    """

    count: int
    has_error_hint: bool


def has_error_hint(message: str) -> bool:
    """Return whether a log message contains error-like textual hints."""
    return bool(ERROR_HINT_RE.search(message) or HTTP_5XX_RE.search(message))


def mine_templates(ambiguous: list[LogEntry]) -> dict[str, list[LogEntry]]:
    """Group ambiguous entries by their mined Drain3 template.

    Args:
        ambiguous: Ambiguous log entries that need template mining.

    Returns:
        A mapping of mined template text to the entries sharing that template.
    """
    config = TemplateMinerConfig()
    miner = TemplateMiner(persistence_handler=MemoryBufferPersistence(), config=config)
    template_entries: dict[str, list[LogEntry]] = defaultdict(list)
    for entry in ambiguous:
        result = miner.add_log_message(entry.message)
        template = str(result.get("template_mined") or entry.message)
        template_entries[template].append(entry)
    return template_entries


def build_template_stats(
    template_entries: dict[str, list[LogEntry]],
) -> tuple[dict[str, TemplateStats], list[int]]:
    """Build count and error-hint statistics for mined templates."""
    stats_by_template: dict[str, TemplateStats] = {}
    all_counts: list[int] = []
    for template, template_logs in template_entries.items():
        count = len(template_logs)
        all_counts.append(count)
        stats_by_template[template] = TemplateStats(
            count=count,
            has_error_hint=any(has_error_hint(item.message) for item in template_logs),
        )
    return stats_by_template, all_counts


def find_anomalous_templates(
    stats_by_template: dict[str, TemplateStats],
    all_counts: list[int],
) -> set[str]:
    """Return templates that look error-like and statistically rare."""
    anomalous_templates: set[str] = set()
    for template, stats in stats_by_template.items():
        if not stats.has_error_hint:
            continue
        if stats.count <= MAX_RARE_TEMPLATE_COUNT:
            anomalous_templates.add(template)
            continue
        if is_statistical_low_outlier(stats.count, all_counts):
            anomalous_templates.add(template)
    return anomalous_templates
