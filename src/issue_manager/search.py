"""Read/query helpers for patrol GitLab issue access."""

from __future__ import annotations

from typing import cast

import httpx

from src.types import GitLabIssue


async def get_issue(base: str, headers: dict[str, str], issue_iid: int) -> GitLabIssue:
    """Fetch one GitLab issue by IID.

    Args:
        base: Project-scoped GitLab issues API endpoint.
        headers: Authentication headers for GitLab requests.
        issue_iid: Project-local issue IID.

    Returns:
        The requested GitLab issue payload.
    """
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        response = await client.get(f"{base}/{issue_iid}")
        response.raise_for_status()
        return cast(GitLabIssue, response.json())


async def search_open_issues(
    base: str,
    headers: dict[str, str],
    patrol_label: str,
    search: str,
    scope: str,
) -> list[GitLabIssue]:
    """Query GitLab for open patrol issues matching a search term."""
    params: dict[str, str] = {
        "state": "opened",
        "labels": patrol_label,
        "search": search,
        "in": scope,
        "per_page": "100",
    }
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        response = await client.get(base, params=params)
        response.raise_for_status()
        return cast(list[GitLabIssue], response.json())


async def list_group_issues(
    group_base: str,
    headers: dict[str, str],
    patrol_label: str,
) -> list[GitLabIssue]:
    """List all open patrol issues visible to the configured GitLab group."""
    all_issues: list[GitLabIssue] = []
    page = 1
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        while True:
            response = await client.get(
                group_base,
                params={
                    "state": "opened",
                    "labels": patrol_label,
                    "per_page": "100",
                    "page": str(page),
                },
            )
            response.raise_for_status()
            items = cast(list[GitLabIssue], response.json())
            if not items:
                break
            all_issues.extend(items)
            page += 1
    return all_issues
