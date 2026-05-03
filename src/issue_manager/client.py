"""GitLab API client used for patrol issue lifecycle operations."""

from __future__ import annotations

from urllib.parse import quote_plus

import httpx

from src.config import GitLabConfig
from src.issue_manager.markers import IssueMarkers
from src.issue_manager.search import get_issue, list_group_issues, search_open_issues
from src.text_tools.sanitize import sanitize_text
from src.types import GitLabIssue


def _append_markers(body: str, markers: IssueMarkers | None) -> str:
    """Append hidden patrol markers to an issue body when configured.

    Args:
        body: Issue description body before marker injection.
        markers: Optional patrol markers embedded in the issue description.

    Returns:
        The description body with marker comments appended and sanitized.
    """
    marker_lines: list[str] = []
    if markers and markers.service:
        marker_lines.append(f"<!-- log-patrol service:{markers.service} -->")
    if markers and markers.fingerprint:
        marker_lines.append(f"<!-- log-patrol fingerprint:{markers.fingerprint} -->")

    marker_block = "\n".join(marker_lines)
    full_body = body.rstrip() + (f"\n\n{marker_block}\n" if marker_block else "\n")
    return sanitize_text(full_body)


class IssueManager:
    """Coordinate GitLab issue operations for patrol-managed incidents.

    This helper centralizes the API endpoints, authentication headers, and
    issue lookup conventions used by the patrol workflow so issue lifecycle
    operations stay consistent across create, update, search, and close calls.

    Attributes:
        cfg: GitLab configuration used to build requests.
        _base: Project-scoped GitLab issues API endpoint.
        _group_base: Group-scoped GitLab issues API endpoint.
        _headers: Authentication headers sent with each GitLab request.
    """

    def __init__(self, cfg: GitLabConfig):
        """Initialize the GitLab API client settings for patrol issue calls.

        Args:
            cfg: GitLab configuration used to build API endpoints and headers.

        Raises:
            ValueError: If the configured GitLab project path is blank.
        """
        self.cfg = cfg
        project_path = (self.cfg.project or "").strip()
        if not project_path:
            raise ValueError(
                "gitlab.project must be set (for example: homelab/prometheus-stack)"
            )
        project_id = quote_plus(project_path)
        self._base = f"{self.cfg.url}/api/v4/projects/{project_id}/issues"
        self._group_base = f"{self.cfg.url}/api/v4/groups/{self.cfg.group}/issues"
        self._headers: dict[str, str] = {"PRIVATE-TOKEN": self.cfg.token}

    async def find_open_issue(self, fingerprint: str) -> GitLabIssue | None:
        """Return the open patrol issue matching a fingerprint, if one exists.

        Args:
            fingerprint: Fingerprint marker to search for in issue descriptions.

        Returns:
            The matching open patrol issue, or `None` if no match exists.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        issues = await search_open_issues(
            self._base,
            self._headers,
            self.cfg.patrol_label,
            fingerprint,
            "description",
        )
        for issue in issues:
            description = issue.get("description", "")
            if f"log-patrol fingerprint:{fingerprint}" in description:
                return issue
        return None

    async def find_open_service_issue(self, service: str) -> GitLabIssue | None:
        """Return the open patrol issue tagged for a service marker, if present.

        Args:
            service: Service marker to search for in issue titles and descriptions.

        Returns:
            The matching open patrol issue, or `None` if no match exists.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        marker = f"log-patrol service:{service}"
        issues = await search_open_issues(
            self._base,
            self._headers,
            self.cfg.patrol_label,
            service,
            "title,description",
        )
        for issue in issues:
            description = issue.get("description", "")
            if marker in description:
                return issue
        return None

    async def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
        markers: IssueMarkers | None = None,
    ) -> int:
        """Create a new patrol issue and return its GitLab issue IID.

        Args:
            title: Issue title to create in GitLab.
            body: Issue description body before embedded patrol markers.
            labels: Labels to attach to the created issue.
            markers: Optional embedded marker metadata for lookup and cleanup.

        Returns:
            The GitLab issue IID for the newly created issue.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        payload = {
            "title": title[:255],
            "description": _append_markers(body, markers),
            "labels": ",".join(labels),
        }
        async with httpx.AsyncClient(timeout=30.0, headers=self._headers) as client:
            response = await client.post(self._base, data=payload)
            response.raise_for_status()
            issue = response.json()
            return int(issue["iid"])

    async def update_issue(
        self,
        issue_iid: int,
        new_labels: list[str],
        append_body: str | None = None,
    ) -> None:
        """Update labels and optionally append a new patrol run section.

        Args:
            issue_iid: GitLab issue IID to update.
            new_labels: Full replacement label set for the issue.
            append_body: Optional patrol run section to append to the description.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        payload: dict[str, str] = {"labels": ",".join(new_labels)}
        if append_body:
            issue = await get_issue(self._base, self._headers, issue_iid)
            desc = sanitize_text((issue.get("description") or "")).rstrip()
            payload["description"] = sanitize_text(f"{desc}\n\n{append_body.strip()}\n")

        async with httpx.AsyncClient(timeout=30.0, headers=self._headers) as client:
            response = await client.put(f"{self._base}/{issue_iid}", data=payload)
            response.raise_for_status()

    async def close_issue(self, issue_iid: int, reason: str) -> None:
        """Add a closing note and close the specified patrol issue.

        Args:
            issue_iid: GitLab issue IID to close.
            reason: Closing note text explaining why the issue was closed.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        async with httpx.AsyncClient(timeout=30.0, headers=self._headers) as client:
            note_resp = await client.post(
                f"{self._base}/{issue_iid}/notes",
                data={"body": reason},
            )
            note_resp.raise_for_status()
            close_resp = await client.put(
                f"{self._base}/{issue_iid}",
                data={"state_event": "close"},
            )
            close_resp.raise_for_status()

    async def list_patrol_issues(self) -> list[GitLabIssue]:
        """List open patrol issues for the configured GitLab group.

        Returns:
            All open patrol issues visible to the configured GitLab group.

        Raises:
            httpx.HTTPError: If the GitLab API request fails.
        """
        return await list_group_issues(
            self._group_base,
            self._headers,
            self.cfg.patrol_label,
        )
