"""Models used by the Loki client package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryWindow:
    """Describe one Loki query pagination window.

    Attributes:
        base_url: Loki base URL for API requests.
        query: LogQL query string.
        query_index: One-based index of the current query.
        query_count: Total number of configured queries.
        start: Inclusive start timestamp in nanoseconds.
        end: Inclusive end timestamp in nanoseconds.
        limit: Per-request result limit.
    """

    base_url: str
    query: str
    query_index: int
    query_count: int
    start: int
    end: int
    limit: int


@dataclass
class LogEntry:
    """Represent one normalized log entry returned from Loki.

    Attributes:
        stream_labels: Loki stream labels associated with the line.
        timestamp_ns: Log timestamp in nanoseconds.
        message: Sanitized log message text.
    """

    stream_labels: dict[str, str]
    timestamp_ns: int
    message: str

    @property
    def service(self) -> str:
        """Return the best available service-style label for the log line.

        Returns:
            The first available service-like label, or `unknown`.
        """
        for key in ("job", "app", "container_name", "host"):
            value = self.stream_labels.get(key)
            if value:
                return value
        return "unknown"
