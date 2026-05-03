"""Issue update helpers for grouped patrol findings."""

from __future__ import annotations

import logging
from typing import Protocol

from src.issue_manager import IssueMarkers, build_issue_body, build_run_section, update_seen_label
from src.loki_client import LogEntry
from src.text_tools import format_issue_title
from src.types import GitLabIssue, StateRow

log = logging.getLogger("log-patrol.main")


class SupportsStateStore(Protocol):
    """Structural contract for state persistence used by workflow helpers."""

    def get(self, fingerprint: str) -> StateRow | None:
        """Load one fingerprint row if present."""

    def upsert(self, fingerprint: str, issue_iid: int, patrol_count: int) -> None:
        """Persist one fingerprint row."""


class SupportsIssueManager(Protocol):
    """Structural contract for issue operations used by workflow helpers."""

    async def find_open_issue(self, fingerprint: str) -> GitLabIssue | None:
        """Find an existing open issue for the fingerprint."""

    async def update_issue(
        self,
        issue_iid: int,
        new_labels: list[str],
        append_body: str | None = None,
    ) -> None:
        """Update one existing issue."""

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
        markers: IssueMarkers | None = None,
    ) -> int:
        """Create a new issue and return its IID."""


async def upsert_issue_for_group(
    fingerprint: str,
    grouped_entries: list[LogEntry],
    *,
    state: SupportsStateStore,
    issues: SupportsIssueManager,
    patrol_label: str,
) -> bool:
    """Update an existing issue or create a new one for one fingerprint.

    Args:
        fingerprint: Stable fingerprint for the grouped log entries.
        grouped_entries: Error entries sharing the fingerprint.
        state: Persistent patrol state store.
        issues: GitLab issue manager.
        patrol_label: Label applied to patrol-managed issues.

    Returns:
        `True` when a new issue was created, else `False`.
    """
    sample_entry = grouped_entries[0]
    state_row = state.get(fingerprint)
    patrol_count = int(state_row["patrol_count"]) + 1 if state_row else 1
    open_issue = await issues.find_open_issue(fingerprint)
    if open_issue:
        issue_iid = int(open_issue["iid"])
        log.info("  Updating existing issue #%d (patrol_count=%d)", issue_iid, patrol_count)
        labels = update_seen_label(open_issue.get("labels", []), patrol_count)
        append_body = build_run_section(fingerprint, sample_entry, grouped_entries, patrol_count)
        await issues.update_issue(issue_iid, labels, append_body=append_body)
        state.upsert(fingerprint, issue_iid, patrol_count)
        return False
    title = format_issue_title(sample_entry, fingerprint)
    log.info("  Creating new issue: %s", title)
    body = build_issue_body(fingerprint, sample_entry, grouped_entries, patrol_count)
    labels = [patrol_label, f"seen-{patrol_count}x"]
    issue_iid = await issues.create_issue(
        title,
        body,
        labels,
        IssueMarkers(fingerprint=fingerprint, service=sample_entry.service),
    )
    log.info("  Created issue #%d", issue_iid)
    state.upsert(fingerprint, issue_iid, patrol_count)
    return True


async def process_fingerprint_groups(
    by_fingerprint: dict[str, list[LogEntry]],
    *,
    state: SupportsStateStore,
    issues: SupportsIssueManager,
    patrol_label: str,
) -> tuple[int, int]:
    """Create or update issues for each fingerprint group.

    Args:
        by_fingerprint: Error entries grouped by fingerprint.
        state: Persistent patrol state store.
        issues: GitLab issue manager.
        patrol_label: Label applied to patrol-managed issues.

    Returns:
        The number of created issues and updated issues.
    """
    created = 0
    updated = 0
    sorted_groups = sorted(by_fingerprint.items(), key=lambda item: len(item[1]), reverse=True)
    for idx, (fingerprint, grouped_entries) in enumerate(sorted_groups, 1):
        sample_entry = grouped_entries[0]
        log.info(
            "[%d/%d] Error found - service=%s fingerprint=%s lines=%d",
            idx,
            len(by_fingerprint),
            sample_entry.service,
            fingerprint[:12],
            len(grouped_entries),
        )
        was_created = await upsert_issue_for_group(
            fingerprint,
            grouped_entries,
            state=state,
            issues=issues,
            patrol_label=patrol_label,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return created, updated
