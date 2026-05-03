"""Live smoke test for Log Patrol external dependencies."""

#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import os
from urllib.parse import quote_plus

import httpx

from src.config import load_config


def check(name: str, ok: bool, detail: str) -> bool:
    """Print a check result line and return the pass/fail boolean.

    Args:
        name: Human-readable check name.
        ok: Whether the check passed.
        detail: Additional detail to print beside the check name.

    Returns:
        The same boolean passed in `ok`.
    """
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")
    return ok


def main() -> int:
    """Run the smoke test and return a process exit code.

    Returns:
        `0` when all checks pass, else `1`.
    """
    cfg = load_config("config.yml")
    token = os.environ.get("GITLAB_TOKEN", "")
    all_ok = True

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        try:
            resp = client.get(f"{cfg.loki.url}/ready")
            all_ok &= check(
                "Loki readiness",
                resp.status_code == 200,
                f"HTTP {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            all_ok &= check("Loki readiness", False, str(exc))

        try:
            resp = client.get("http://localhost:11434/api/tags")
            present = cfg.llm.model in str(resp.text)
            all_ok &= check(
                "Ollama tags",
                resp.status_code == 200 and present,
                f"HTTP {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            all_ok &= check("Ollama tags", False, str(exc))

        try:
            headers = {"PRIVATE-TOKEN": token}
            resp = client.get(
                f"{cfg.gitlab.url}/api/v4/groups/{cfg.gitlab.group}",
                headers=headers,
            )
            all_ok &= check(
                "GitLab group API",
                resp.status_code == 200,
                f"HTTP {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            all_ok &= check("GitLab group API", False, str(exc))

        if token:
            try:
                headers = {"PRIVATE-TOKEN": token}
                title = f"log-patrol smoke {datetime.now(timezone.utc).isoformat()}"
                project = quote_plus(cfg.gitlab.project)
                create = client.post(
                    f"{cfg.gitlab.url}/api/v4/projects/{project}/issues",
                    headers=headers,
                    data={
                        "title": title,
                        "description": "Smoke test issue. Closing immediately.",
                        "labels": cfg.gitlab.patrol_label,
                    },
                )
                if create.status_code == 201:
                    iid = create.json()["iid"]
                    close = client.put(
                        f"{cfg.gitlab.url}/api/v4/projects/{project}/issues/{iid}",
                        headers=headers,
                        data={"state_event": "close"},
                    )
                    all_ok &= check(
                        "GitLab create+close issue",
                        close.status_code == 200,
                        f"iid={iid}",
                    )
                else:
                    all_ok &= check(
                        "GitLab create+close issue",
                        False,
                        f"create HTTP {create.status_code}",
                    )
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                all_ok &= check("GitLab create+close issue", False, str(exc))
        else:
            all_ok &= check("GitLab create+close issue", False, "GITLAB_TOKEN is missing")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
