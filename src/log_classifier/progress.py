"""Progress and statistical helpers for log classification."""

from __future__ import annotations

import math
from statistics import median

from src.log_classifier.constants import MIN_TEMPLATES_FOR_ROBUST_SCORING, PROGRESS_STEP_PERCENT


def progress_marks(total: int) -> list[int]:
    """Emit progress checkpoints for a batch size.

    Args:
        total: Total number of entries in the batch.

    Returns:
        One-based progress checkpoint positions.
    """
    if total <= 0:
        return []
    marks: list[int] = []
    for percent in range(PROGRESS_STEP_PERCENT, 101, PROGRESS_STEP_PERCENT):
        mark = math.ceil((total * percent) / 100)
        if not marks or mark != marks[-1]:
            marks.append(mark)
    return marks


def is_statistical_low_outlier(count: int, all_counts: list[int]) -> bool:
    """Return whether a template count is a robust low-frequency outlier.

    Args:
        count: Frequency count for one template.
        all_counts: Frequency counts for all templates.

    Returns:
        `True` when the template frequency is an outlier on the low end.
    """
    if len(all_counts) < MIN_TEMPLATES_FOR_ROBUST_SCORING:
        return False
    log_counts = [math.log1p(value) for value in all_counts]
    center = median(log_counts)
    abs_dev = [abs(value - center) for value in log_counts]
    mad = median(abs_dev)
    if mad == 0:
        return False
    robust_z = (math.log1p(count) - center) / (1.4826 * mad)
    return robust_z <= -2.5
