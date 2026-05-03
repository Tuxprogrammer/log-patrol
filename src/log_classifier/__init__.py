"""Deterministic-first classification helpers for patrol log entries."""

from src.log_classifier.core import classify_entries
from src.log_classifier.progress import progress_marks as _progress_marks

__all__ = ["classify_entries", "_progress_marks"]
