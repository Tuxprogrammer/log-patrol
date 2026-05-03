"""Tests for stale patrol issue cleanup behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.issue_manager import close_stale_issues
from src.types import GitLabIssue


class _DummyIssueManager:
    """Implement the stale-cleaner issue protocol for isolated tests.

    This lightweight double exposes a fixed issue list and records close
    operations so stale-cleaner tests can verify which issues would be closed
    and why, without involving the real GitLab issue manager.

    Attributes:
        _issues: Open patrol issues presented to the stale cleaner.
        closed: Recorded `(issue_iid, reason)` pairs closed by the cleaner.
    """

    def __init__(self, issues: list[GitLabIssue]) -> None:
        """Store the issue list and capture closed issues.

        Args:
            issues: Open patrol issues exposed by the test double.
        """
        self._issues = issues
        self.closed: list[tuple[int, str]] = []

    async def list_patrol_issues(self) -> list[GitLabIssue]:
        """Return the current open patrol issues for the test case.

        Returns:
            The issue list configured for the test double.
        """
        return self._issues

    async def close_issue(self, issue_iid: int, reason: str) -> None:
        """Record the closed issue identifier and reason.

        Args:
            issue_iid: GitLab issue IID that the cleaner closed.
            reason: Closing reason emitted by the cleaner.
        """
        self.closed.append((issue_iid, reason))


class _DummyState:
    """Implement the stale-cleaner state protocol for isolated tests.

    The double tracks deleted keys so tests can assert which fingerprint or
    service entries the stale cleaner would remove from persistent state.

    Attributes:
        deleted: Fingerprint or service keys deleted during cleanup.
    """

    def __init__(self) -> None:
        """Initialize the deleted state-key capture list."""
        self.deleted: list[str] = []

    def delete(self, fingerprint: str) -> None:
        """Record the deleted fingerprint or service state key.

        Args:
            fingerprint: Fingerprint or service key deleted by the cleaner.
        """
        self.deleted.append(fingerprint)

    def get(self, fingerprint: str) -> None:
        """Return no stored state for the requested fingerprint.

        Args:
            fingerprint: Fingerprint or service key to look up.
        """
        _ = fingerprint


async def test_close_stale_issues_closes_old_only() -> None:
    """Closes only issues whose updated timestamps are older than the cutoff."""
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    fresh = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    issues: list[GitLabIssue] = [
        {
            "iid": 10,
            "updated_at": old,
            "description": "x\n<!-- log-patrol fingerprint:abcdef0123456789 -->",
        },
        {
            "iid": 11,
            "updated_at": fresh,
            "description": "x\n<!-- log-patrol fingerprint:fedcba9876543210 -->",
        },
    ]
    mgr = _DummyIssueManager(issues)
    state = _DummyState()
    closed = await close_stale_issues(mgr, state, stale_days=3)
    assert closed == [10]
    assert state.deleted == ["abcdef0123456789"]


async def test_close_stale_issues_deletes_service_state_key() -> None:
    """Deletes the legacy service state key when no fingerprint marker exists."""
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    issues: list[GitLabIssue] = [
        {
            "iid": 12,
            "updated_at": old,
            "description": "x\n<!-- log-patrol service:gitlab-webservice -->",
        }
    ]
    mgr = _DummyIssueManager(issues)
    state = _DummyState()
    closed = await close_stale_issues(mgr, state, stale_days=3)
    assert closed == [12]
    assert state.deleted == ["service::gitlab-webservice"]
