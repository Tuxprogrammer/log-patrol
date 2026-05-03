"""Top-level log fetching orchestration for the Loki client."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from src.config import LokiConfig
from src.loki_client.models import LogEntry, QueryWindow
from src.loki_client.pagination import fetch_query_pages

log = logging.getLogger("log-patrol.loki")


def _build_query_window(
    cfg: LokiConfig,
    query: str,
    query_index: int,
    bounds: tuple[int, int],
    limit: int,
) -> QueryWindow:
    """Build pagination metadata for one configured Loki query.

    Args:
        cfg: Loki connection and query settings.
        query: LogQL query string.
        query_index: One-based index of the current query.
        bounds: Inclusive start and end timestamps in nanoseconds.
        limit: Per-request result limit.

    Returns:
        Immutable metadata describing the query pagination window.
    """
    start, end = bounds
    return QueryWindow(
        base_url=cfg.url,
        query=query,
        query_index=query_index,
        query_count=len(cfg.queries),
        start=start,
        end=end,
        limit=limit,
    )


async def fetch_logs(cfg: LokiConfig) -> list[LogEntry]:
    """Fetch and deduplicate log entries from all configured Loki queries.

    Args:
        cfg: Loki connection and query settings.

    Returns:
        Deduplicated log entries collected across all configured queries.

    Raises:
        httpx.HTTPError: If a Loki API request fails.
    """
    now = datetime.now(timezone.utc)
    start = int((now - timedelta(minutes=cfg.lookback_minutes)).timestamp() * 1_000_000_000)
    end = int(now.timestamp() * 1_000_000_000)
    limit = 5000
    out: list[LogEntry] = []
    seen: set[tuple[int, tuple[tuple[str, str], ...], str]] = set()
    log.debug("Queries: %s  start=%s  end=%s  limit=%d", cfg.queries, start, end, limit)
    async with httpx.AsyncClient(timeout=30.0) as client:
        total_pages = 0
        for query_index, query in enumerate(cfg.queries, 1):
            window = _build_query_window(
                cfg,
                query,
                query_index,
                (start, end),
                limit,
            )
            total_pages += await fetch_query_pages(client, window, seen=seen, out=out)
    log.info("fetch_logs complete: %d total entries across %d page(s)", len(out), total_pages)
    return out
