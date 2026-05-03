"""Tests for low-level GitLab issue query helpers."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from src.issue_manager.search import get_issue, list_group_issues, search_open_issues
from tests.http_stubs import ResponseStub


class _SearchClientStub:
    """Return canned GET responses for issue search helpers.

    Attributes:
        responses: Ordered response payloads returned on successive GET calls.
        calls: Recorded request URLs and params.
    """

    def __init__(self, responses: list[object]) -> None:
        """Store the ordered GET responses.

        Args:
            responses: Payloads returned on successive GET calls.
        """
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    async def __aenter__(self) -> _SearchClientStub:
        """Enter the async client context.

        Returns:
            This stub instance.
        """
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        """Exit the async client context without suppression.

        Args:
            exc_type: Exception type raised in the context, if any.
            exc: Exception instance raised in the context, if any.
            tb: Traceback object for the raised exception, if any.

        Returns:
            `False` so any exception propagates.
        """
        return False

    async def get(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
    ) -> ResponseStub:
        """Return the next canned response payload.

        Args:
            url: Request URL.
            params: Query params for the request.

        Returns:
            A stub response wrapping the next payload.
        """
        self.calls.append((url, params))
        return ResponseStub(self.responses.pop(0))


async def test_get_issue_and_search_open_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetches a single issue and searches open patrol issues.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    client = _SearchClientStub(
        [
            {"iid": 7, "description": "x"},
            [{"iid": 8, "description": "y"}],
        ]
    )
    monkeypatch.setattr("src.issue_manager.search.httpx.AsyncClient", lambda **kwargs: client)

    issue = await get_issue("https://gitlab/api/v4/projects/1/issues", {"PRIVATE-TOKEN": "x"}, 7)
    matches = await search_open_issues(
        "https://gitlab/api/v4/projects/1/issues",
        {"PRIVATE-TOKEN": "x"},
        "example-patrol",
        "needle",
        "title",
    )

    assert issue["iid"] == 7
    assert matches[0]["iid"] == 8
    assert client.calls[1][1] == {
        "state": "opened",
        "labels": "example-patrol",
        "search": "needle",
        "in": "title",
        "per_page": "100",
    }


async def test_list_group_issues_paginates_until_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aggregates all open group issues across paginated GitLab responses.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    client = _SearchClientStub(
        [
            [{"iid": 1, "description": "a"}],
            [{"iid": 2, "description": "b"}],
            [],
        ]
    )
    monkeypatch.setattr("src.issue_manager.search.httpx.AsyncClient", lambda **kwargs: client)

    issues = await list_group_issues(
        "https://gitlab/api/v4/groups/1/issues",
        {"PRIVATE-TOKEN": "x"},
        "example-patrol",
    )

    assert [issue["iid"] for issue in issues] == [1, 2]
    last_params = client.calls[-1][1]
    assert last_params is not None
    assert last_params["page"] == "3"
