"""Stale patrol issue cleanup helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Protocol

from src.types import GitLabIssue

FINGERPRINT_RE = re.compile(r"log-patrol fingerprint:([a-f0-9]{16})")
SERVICE_RE = re.compile(r"log-patrol service:([^\s]+)")


class _PatrolIssueManager(Protocol):
    """Describe the issue-manager behavior required by stale cleanup."""

    async def list_patrol_issues(self) -> list[GitLabIssue]:
        """List open patrol issues that may need stale cleanup."""

    async def close_issue(self, issue_iid: int, reason: str) -> None:
        """Close the given issue and record the supplied reason."""


class _PatrolStateStore(Protocol):
    """Describe the state-store behavior required by stale cleanup."""

    def get(self, fingerprint: str) -> object | None:
        """Return stored state for a fingerprint or service key when present."""

    def delete(self, fingerprint: str) -> None:
        """Remove persisted state for a fingerprint or service key."""


def _parse_updated_at(updated_at: str) -> datetime:
    return datetime.fromisoformat(updated_at.replace("Z", "+00:00"))


async def close_stale_issues(
    issue_manager: _PatrolIssueManager,
    state: _PatrolStateStore,
    stale_days: int,
) -> list[int]:
    """Close inactive patrol issues and drop their persisted state keys.

    Args:
        issue_manager: Issue manager used to list and close patrol issues.
        state: State store used to remove stale fingerprint or service keys.
        stale_days: Age threshold for closing an inactive issue.

    Returns:
        GitLab issue IIDs that were closed during this cleanup pass.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    closed: list[int] = []
    issues = await issue_manager.list_patrol_issues()
    reason = (
        f"Closed by log-patrol: no activity for {stale_days}+ days.\n"
        "If this problem recurs, a new issue will be opened automatically."
    )
    for issue in issues:
        updated_raw = issue.get("updated_at")
        if not updated_raw:
            continue
        if _parse_updated_at(updated_raw) >= cutoff:
            continue
        iid = int(issue["iid"])
        await issue_manager.close_issue(iid, reason)
        closed.append(iid)
        description = issue.get("description", "")
        match = FINGERPRINT_RE.search(description)
        if match:
            state.delete(match.group(1))
            continue
        service_match = SERVICE_RE.search(description)
        if service_match:
            service = service_match.group(1).strip()
            state.delete(f"service::{service}")
    return closed
