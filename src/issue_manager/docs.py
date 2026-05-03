"""Issue body rendering helpers for patrol-managed incidents."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from src.loki_client.models import LogEntry
from src.text_tools.json_tools import extract_display_message, parse_message_json, truncate_text


def _escape_md(text: str) -> str:
    """Escape Markdown table delimiters and flatten embedded newlines.

    Args:
        text: Raw text destined for a Markdown table cell.

    Returns:
        Escaped single-line Markdown-safe text.
    """
    return text.replace("|", "\\|").replace("\n", " ")


def _build_metadata(entry: LogEntry) -> dict[str, Any]:
    """Build metadata rendered alongside sample log lines in issues.

    Args:
        entry: Log entry to summarize.

    Returns:
        Metadata fields rendered beside sample log lines in an issue body.
    """
    payload = parse_message_json(entry.message)
    meta: dict[str, Any] = {
        "service": entry.service,
        "timestamp_ns": entry.timestamp_ns,
        "stream_labels": entry.stream_labels,
    }
    if not payload:
        return meta

    redacted = dict(payload)
    for key in ("message", "msg", "log", "event_message", "description"):
        redacted.pop(key, None)
    meta["fields"] = redacted
    return meta


def build_run_section(
    fingerprint: str,
    sample_entry: LogEntry,
    grouped_entries: list[LogEntry],
    patrol_count: int,
) -> str:
    """Render one appended patrol run section for a fingerprint issue."""
    rows = [
        (
            f"| `{fingerprint[:12]}` | {len(grouped_entries)} | "
            f"{_escape_md(truncate_text(sample_entry.message))} |"
        )
    ]
    sample_entries = grouped_entries[:10]
    sample_logs = "\n\n---\n\n".join(extract_display_message(entry) for entry in sample_entries)
    metadata = [_build_metadata(entry) for entry in sample_entries]
    metadata_json = json.dumps(metadata, indent=2, sort_keys=True)
    rows_block = "\n".join(rows)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        f"### Patrol Run {patrol_count} ({ts})\n\n"
        f"- **Service:** `{sample_entry.service}`\n"
        f"- **Fingerprint:** `{fingerprint}`\n"
        f"- **Matches in this run:** `{len(grouped_entries)}`\n\n"
        "#### Fingerprint Summary\n\n"
        "| Fingerprint | Count | Example |\n"
        "|---|---:|---|\n"
        f"{rows_block}\n\n"
        "#### Sample Log Lines\n\n"
        "```text\n"
        f"{sample_logs}\n"
        "```\n\n"
        "#### Log Metadata\n\n"
        "```json\n"
        f"{metadata_json}\n"
        "```\n"
    )


def build_issue_body(
    fingerprint: str,
    sample_entry: LogEntry,
    grouped_entries: list[LogEntry],
    patrol_count: int,
) -> str:
    """Build the initial GitLab issue body for one fingerprint."""
    return (
        f"## Log Patrol - `{sample_entry.service}`\n\n"
        "This issue tracks recurring error-like logs for a single fingerprint. "
        "Each patrol run appends a new section below.\n\n"
        + build_run_section(fingerprint, sample_entry, grouped_entries, patrol_count)
    )
