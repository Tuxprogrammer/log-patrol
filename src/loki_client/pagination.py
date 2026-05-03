"""Pagination helpers for Loki query_range requests."""

from __future__ import annotations

import logging
from typing import cast

import httpx

from src.loki_client.models import LogEntry, QueryWindow
from src.text_tools.sanitize import sanitize_text

log = logging.getLogger("log-patrol.loki")


def append_stream_values(
    stream: dict[str, object],
    seen: set[tuple[int, tuple[tuple[str, str], ...], str]],
    out: list[LogEntry],
) -> tuple[int, int, int]:
    """Append unseen values from one Loki stream and return page counters.

    Args:
        stream: Loki result stream containing labels and value pairs.
        seen: Dedupe keys for log entries already emitted.
        out: Collected normalized log entries.

    Returns:
        The maximum timestamp seen, total rows scanned, and new rows emitted.
    """
    labels = cast(dict[str, str], stream.get("stream", {}))
    label_key = tuple(sorted(labels.items()))
    max_ts = 0
    page_rows = 0
    new_rows = 0
    values = cast(list[tuple[str, str]], stream.get("values", []))
    for ts_str, msg in values:
        ts_ns = int(ts_str)
        clean_msg = sanitize_text(msg)
        max_ts = max(max_ts, ts_ns)
        page_rows += 1
        dedupe_key = (ts_ns, label_key, clean_msg)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(LogEntry(stream_labels=labels, timestamp_ns=ts_ns, message=clean_msg))
        new_rows += 1
    return max_ts, page_rows, new_rows


async def fetch_query_page_results(
    client: httpx.AsyncClient,
    window: QueryWindow,
    next_start: int,
) -> list[dict[str, object]]:
    """Fetch one page of Loki results for the provided query window.

    Args:
        client: Async HTTP client used for Loki requests.
        window: Immutable query window metadata for this pagination pass.
        next_start: Nanosecond timestamp to use as the next page start.

    Returns:
        Raw Loki result streams for the requested page.

    Raises:
        httpx.HTTPError: If the Loki API request fails.
    """
    response = await client.get(
        f"{window.base_url}/loki/api/v1/query_range",
        params={
            "query": window.query,
            "start": str(next_start),
            "end": str(window.end),
            "limit": str(window.limit),
            "direction": "forward",
        },
    )
    response.raise_for_status()
    payload = cast(dict[str, object], response.json())
    data = cast(dict[str, object], payload.get("data", {}))
    return cast(list[dict[str, object]], data.get("result", []))


async def fetch_query_pages(
    client: httpx.AsyncClient,
    window: QueryWindow,
    seen: set[tuple[int, tuple[tuple[str, str], ...], str]],
    out: list[LogEntry],
) -> int:
    """Fetch all pages for one Loki query and return the page count.

    Args:
        client: Async HTTP client used for Loki requests.
        window: Immutable query window metadata for this pagination pass.
        seen: Dedupe keys for log entries already emitted.
        out: Collected normalized log entries.

    Returns:
        The number of pages fetched for the query.

    Raises:
        httpx.HTTPError: If a Loki API request fails.
    """
    page = 0
    pages = 0
    next_start = window.start
    while next_start <= window.end:
        page += 1
        pages += 1
        log.debug(
            "Fetching query %d/%d page %d (next_start=%d, collected=%d so far)...",
            window.query_index,
            window.query_count,
            page,
            next_start,
            len(out),
        )
        results = await fetch_query_page_results(client, window, next_start)
        log.debug(
            "  Query %d page %d: Loki returned %d streams",
            window.query_index,
            page,
            len(results),
        )
        if not results:
            log.debug("  Query %d exhausted, stopping pagination", window.query_index)
            break
        max_ts = next_start
        page_rows = 0
        new_rows = 0
        for stream in results:
            stream_max_ts, stream_rows, stream_new_rows = append_stream_values(stream, seen, out)
            max_ts = max(max_ts, stream_max_ts)
            page_rows += stream_rows
            new_rows += stream_new_rows
        log.debug(
            "  Query %d page %d: %d rows, %d new rows, max_ts=%d",
            window.query_index,
            page,
            page_rows,
            new_rows,
            max_ts,
        )
        if not page_rows:
            log.debug(
                "  Zero rows on query %d page %d, stopping pagination",
                window.query_index,
                page,
            )
            break
        next_start = max_ts + 1
    return pages
