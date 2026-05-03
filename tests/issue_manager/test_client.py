"""Tests for GitLab issue manager helper behavior."""

from __future__ import annotations

import pytest

from src.config import GitLabConfig
from src.issue_manager import IssueManager, IssueMarkers, update_seen_label
from tests.http_stubs import ResponseStub


class _IssueClientStub:
    """Simulate the subset of the async GitLab client used in issue tests.

    The stub records each request and returns canned payloads so the tests can
    assert how the issue manager interacts with GitLab endpoints without making
    external network calls.

    Attributes:
        calls: Ordered record of HTTP verb, URL, and payload tuples.
    """

    def __init__(self) -> None:
        """Initialize the captured request list."""
        self.calls: list[tuple[str, str, object]] = []

    async def __aenter__(self) -> _IssueClientStub:
        """Enter the async client context.

        Returns:
            This stub instance.
        """
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        """Exit the async client context without suppressing exceptions.

        Args:
            exc_type: Exception type raised in the context, if any.
            exc: Exception instance raised in the context, if any.
            tb: Traceback object for the raised exception, if any.

        Returns:
            `False` so any exception propagates.
        """
        return False

    async def get(self, url: str, params: object = None) -> ResponseStub:
        """Return canned issue responses for GET requests."""
        self.calls.append(("get", url, params))
        if url.endswith("/123"):
            return ResponseStub({"iid": 123, "description": "base"})
        return ResponseStub(
            [
                {
                    "iid": 123,
                    "labels": ["example-patrol", "seen-1x"],
                    "description": "x\n<!-- log-patrol fingerprint:abcdef0123456789 -->",
                }
            ]
        )

    async def post(self, url: str, data: object = None) -> ResponseStub:
        """Return canned issue creation or note responses for POST requests."""
        self.calls.append(("post", url, data))
        if url.endswith("/notes"):
            return ResponseStub({"id": 99})
        return ResponseStub({"iid": 123})

    async def put(self, url: str, data: object = None) -> ResponseStub:
        """Return a canned success response for PUT requests."""
        self.calls.append(("put", url, data))
        return ResponseStub({"iid": 123})


async def test_issue_manager_create_update_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Creates, updates, and closes issues through the HTTP client stub.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    client = _IssueClientStub()
    monkeypatch.setattr("src.issue_manager.client.httpx.AsyncClient", lambda **kwargs: client)
    cfg = GitLabConfig(
        url="https://gitlab.example.com",
        token="token",
        group="example-group",
        project="example-group/example-project",
        patrol_label="example-patrol",
        stale_days=3,
    )
    mgr = IssueManager(cfg)
    issue = await mgr.find_open_issue("abcdef0123456789")
    assert issue is not None
    service_issue = await mgr.find_open_service_issue("system")
    assert service_issue is None
    iid = await mgr.create_issue(
        "title",
        "body",
        ["example-patrol", "seen-1x"],
        IssueMarkers(fingerprint="abcdef0123456789", service="system"),
    )
    assert iid == 123
    await mgr.update_issue(123, ["example-patrol", "seen-2x"], append_body="update")
    await mgr.close_issue(123, "stale")
    methods = [c[0] for c in client.calls]
    assert "post" in methods and "put" in methods and "get" in methods


def test_update_seen_label() -> None:
    """Replaces old seen-count labels while preserving unrelated labels."""
    labels = update_seen_label(["example-patrol", "seen-2x", "foo"], 4)
    assert "seen-2x" not in labels
    assert "seen-4x" in labels
    assert "foo" in labels
