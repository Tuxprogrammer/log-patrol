"""Tests for patrol workflow helper functions."""

from __future__ import annotations

import pytest

from src.issue_manager import IssueMarkers
from src.loki_client import LogEntry
from src.patrol_workflow import (
    filter_excluded_entries,
    group_entries_by_fingerprint,
    llm_sentiment_gate,
    process_fingerprint_groups,
    upsert_issue_for_group,
)
from src.types import GitLabIssue, StateRow


class _StateStub:
    """Provide the minimal state-store API used by issue update helpers.

    Attributes:
        rows: Stored fingerprint state keyed by fingerprint.
        upserts: Recorded upsert calls.
    """

    def __init__(self, rows: dict[str, StateRow] | None = None) -> None:
        """Initialize the stored rows and captured upserts.

        Args:
            rows: Optional initial state rows keyed by fingerprint.
        """
        self.rows = rows or {}
        self.upserts: list[tuple[str, int, int]] = []

    def get(self, fingerprint: str) -> StateRow | None:
        """Return the stored state row for one fingerprint.

        Args:
            fingerprint: Fingerprint to load.

        Returns:
            The stored state row when present.
        """
        return self.rows.get(fingerprint)

    def upsert(self, fingerprint: str, issue_iid: int, patrol_count: int) -> None:
        """Record an upsert operation.

        Args:
            fingerprint: Stable fingerprint being updated.
            issue_iid: GitLab issue IID stored for the fingerprint.
            patrol_count: New patrol occurrence count.
        """
        self.upserts.append((fingerprint, issue_iid, patrol_count))


class _IssueStub:
    """Provide the minimal GitLab issue API used by workflow helpers.

    Attributes:
        open_issue: Existing issue returned by `find_open_issue`.
        updated: Recorded update calls.
        created: Recorded create calls.
    """

    def __init__(self, open_issue: GitLabIssue | None = None) -> None:
        """Initialize the issue stub.

        Args:
            open_issue: Optional existing issue payload.
        """
        self.open_issue = open_issue
        self.updated: list[tuple[int, list[str], str]] = []
        self.created: list[tuple[str, str, list[str], object]] = []

    async def find_open_issue(self, fingerprint: str) -> GitLabIssue | None:
        """Return the configured open issue if present.

        Args:
            fingerprint: Fingerprint being searched.

        Returns:
            The configured open issue payload.
        """
        _ = fingerprint
        return self.open_issue

    async def update_issue(
        self,
        issue_iid: int,
        new_labels: list[str],
        append_body: str | None = None,
    ) -> None:
        """Record an update request.

        Args:
            issue_iid: Issue IID being updated.
            new_labels: Replacement labels for the issue.
            append_body: New markdown appended to the issue body.
        """
        self.updated.append((issue_iid, new_labels, append_body or ""))

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
        markers: IssueMarkers | None = None,
    ) -> int:
        """Record a create request and return a canned IID.

        Args:
            title: Issue title.
            body: Issue body.
            labels: Initial labels.
            markers: Optional marker object appended to the body.

        Returns:
            A canned issue IID.
        """
        self.created.append((title, body, labels, markers))
        return 900


class _LLMStub:
    """Return canned LLM verdicts for workflow gate tests.

    Attributes:
        verdicts: Ordered verdicts returned on successive calls.
        calls: Recorded `(service, message)` call tuples.
    """

    def __init__(self, verdicts: list[bool]) -> None:
        """Store the ordered LLM verdicts.

        Args:
            verdicts: Verdicts returned on each classify call.
        """
        self.verdicts = verdicts
        self.calls: list[tuple[str, str]] = []

    async def classify_is_error(self, service: str, message: str) -> bool:
        """Return the next canned verdict.

        Args:
            service: Service name passed by the helper.
            message: Message text passed by the helper.

        Returns:
            The next configured verdict.
        """
        self.calls.append((service, message))
        return self.verdicts.pop(0)


def test_filter_excluded_entries_and_grouping() -> None:
    """Drops regex-matched entries and groups the survivors by fingerprint."""
    entries = [
        LogEntry({"job": "api", "host": "node1"}, 1, "ignore me"),
        LogEntry({"job": "api", "host": "node1"}, 2, "database timeout id 1"),
        LogEntry({"job": "api", "host": "node1"}, 3, "database timeout id 9"),
    ]

    kept, dropped = filter_excluded_entries(entries, ["ignore"])
    groups = group_entries_by_fingerprint(kept)

    assert dropped == 1
    assert kept == entries[1:]
    assert len(groups) == 2
    assert sum(len(group) for group in groups.values()) == 2


async def test_llm_gate_handles_empty_and_progress(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Returns early for empty input and logs coarse progress for batches.

    Args:
        caplog: Pytest log capture fixture.
    """
    assert await llm_sentiment_gate([], _LLMStub([])) == []

    entries = [LogEntry({"job": "api"}, idx, f"msg {idx}") for idx in range(1, 12)]
    llm = _LLMStub([True, False, True, False, True, False, True, False, True, False, True])
    with caplog.at_level("INFO"):
        kept = await llm_sentiment_gate(entries, llm)

    assert [entry.message for entry in kept] == [
        "msg 1",
        "msg 3",
        "msg 5",
        "msg 7",
        "msg 9",
        "msg 11",
    ]
    assert "LLM sentiment progress: 10/11" in caplog.text
    assert "LLM sentiment progress: 11/11" in caplog.text


async def test_upsert_issue_for_group_updates_existing_issue() -> None:
    """Appends a patrol run section when the fingerprint already has an issue."""
    entries = [LogEntry({"job": "api"}, 1, "database timeout")]
    state = _StateStub({"finger": {"issue_iid": 123, "patrol_count": 2, "last_seen": ""}})
    issues = _IssueStub({"iid": 123, "labels": ["example-patrol", "seen-2x"]})

    created = await upsert_issue_for_group(
        "finger",
        entries,
        state=state,
        issues=issues,
        patrol_label="example-patrol",
    )

    assert created is False
    assert state.upserts == [("finger", 123, 3)]
    assert issues.updated[0][0] == 123
    assert "seen-3x" in issues.updated[0][1]
    assert "### Patrol Run 3" in issues.updated[0][2]


async def test_upsert_issue_for_group_creates_new_issue() -> None:
    """Creates a new issue and persists the returned issue IID."""
    entries = [LogEntry({"job": "api"}, 1, "database timeout")]
    state = _StateStub()
    issues = _IssueStub()

    created = await upsert_issue_for_group(
        "finger",
        entries,
        state=state,
        issues=issues,
        patrol_label="example-patrol",
    )

    assert created is True
    assert state.upserts == [("finger", 900, 1)]
    assert issues.created
    assert issues.created[0][0].startswith("[")


async def test_process_fingerprint_groups_counts_created_and_updated() -> None:
    """Sorts groups by size and returns separate create and update totals."""
    groups = {
        "smaller": [LogEntry({"job": "api"}, 2, "m2")],
        "bigger": [LogEntry({"job": "api"}, 1, "m1"), LogEntry({"job": "api"}, 3, "m3")],
    }
    state = _StateStub()
    issues = _IssueStub()
    calls: list[str] = []

    async def _fake_upsert(
        fingerprint: str,
        grouped_entries: list[LogEntry],
        *,
        state: _StateStub,
        issues: _IssueStub,
        patrol_label: str,
    ) -> bool:
        _ = grouped_entries, state, issues, patrol_label
        calls.append(fingerprint)
        return fingerprint == "bigger"

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("src.patrol_workflow.issue_updates.upsert_issue_for_group", _fake_upsert)
    try:
        created, updated = await process_fingerprint_groups(
            groups,
            state=state,
            issues=issues,
            patrol_label="example-patrol",
        )
    finally:
        monkeypatch.undo()

    assert calls == ["bigger", "smaller"]
    assert (created, updated) == (1, 1)
