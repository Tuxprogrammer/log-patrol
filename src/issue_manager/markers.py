"""Marker metadata embedded into patrol issue descriptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssueMarkers:
    """Store optional hidden markers embedded into issue descriptions.

    Attributes:
        fingerprint: Stable fingerprint marker for a patrol issue.
        service: Service marker stored in the issue description.
    """

    fingerprint: str | None = None
    service: str | None = None
