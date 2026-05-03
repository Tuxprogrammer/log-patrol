"""Label utilities for patrol-managed GitLab issues."""

from __future__ import annotations


def update_seen_label(existing_labels: list[str], new_count: int) -> list[str]:
    """Replace any existing seen-count label with the latest patrol count.

    Args:
        existing_labels: Existing GitLab issue labels.
        new_count: Patrol occurrence count to encode in the seen label.

    Returns:
        The updated label list with a single current seen-count label.
    """
    labels = [label for label in existing_labels if not label.startswith("seen-")]
    labels.append(f"seen-{new_count}x")
    return labels
