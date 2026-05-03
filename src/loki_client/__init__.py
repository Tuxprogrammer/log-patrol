"""Loki query helpers and the normalized log entry model."""

from src.loki_client.fetch import fetch_logs
from src.loki_client.models import LogEntry

__all__ = ["LogEntry", "fetch_logs"]
