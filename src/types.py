"""Typed dictionaries shared across Log Patrol modules."""

from __future__ import annotations

from typing import TypedDict


class GitLabIssue(TypedDict, total=False):
    """Represent the GitLab issue fields consumed by the patrol workflow.

    The application does not need the full GitLab issue schema, so this typed
    dictionary narrows the response surface to the fields referenced by issue
    management, stale cleanup, and tests.

    Attributes:
        iid: Project-local issue identifier returned by GitLab.
        labels: Labels currently attached to the issue.
        description: Markdown description body stored on the issue.
        updated_at: ISO 8601 timestamp of the most recent issue update.
    """

    iid: int | str
    labels: list[str]
    description: str
    updated_at: str


class StateRow(TypedDict):
    """Represent the persisted state associated with one fingerprint.

    This typed dictionary matches the SQLite row shape returned by the state
    store when looking up an existing patrol issue mapping.

    Attributes:
        issue_iid: GitLab issue IID associated with the fingerprint.
        patrol_count: Number of patrol runs that have seen the fingerprint.
        last_seen: ISO 8601 timestamp of the most recent observation.
    """

    issue_iid: int
    patrol_count: int
    last_seen: str


class StateRecord(StateRow):
    """Represent a full persisted patrol state record including the key.

    This extends [StateRow] with the fingerprint column so bulk state reads can
    return both the record payload and the lookup key in one object.

    Attributes:
        fingerprint: Stable fingerprint key for the tracked log pattern.
        issue_iid: GitLab issue IID associated with the fingerprint.
        patrol_count: Number of patrol runs that have seen the fingerprint.
        last_seen: ISO 8601 timestamp of the most recent observation.
    """

    fingerprint: str
