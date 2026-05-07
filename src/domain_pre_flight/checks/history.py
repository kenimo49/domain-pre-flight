"""Past-content history checks via the Internet Archive Wayback Machine.

Free, no-auth public API:
- https://archive.org/wayback/available?url=<domain>
- https://web.archive.org/cdx/search/cdx?url=<domain>&output=json&limit=...

We use both: ``available`` for a quick snapshot ping, and the CDX API for
counting and bracketing the first/last archived timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests

WAYBACK_AVAILABLE = "https://archive.org/wayback/available"
WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"

DEFAULT_TIMEOUT = 10  # seconds


@dataclass
class HistoryReport:
    domain: str
    has_archive: bool
    snapshot_count: int
    first_seen: str | None
    last_seen: str | None
    age_days: int | None
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _parse_wayback_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S")
    except (ValueError, TypeError):
        return None


def check_history(domain: str, timeout: int = DEFAULT_TIMEOUT) -> HistoryReport:
    """Query the Wayback Machine for archived snapshots of ``domain``."""
    domain = domain.strip().lower().rstrip(".")
    issues: list[str] = []
    notes: list[str] = []
    raw: dict[str, Any] = {}

    snapshot_count = 0
    first_seen: str | None = None
    last_seen: str | None = None
    age_days: int | None = None
    has_archive = False

    try:
        cdx_resp = requests.get(
            WAYBACK_CDX,
            params={
                "url": domain,
                "output": "json",
                "fl": "timestamp,statuscode,mimetype",
                "limit": 5000,
                "filter": "statuscode:200",
            },
            timeout=timeout,
            headers={"User-Agent": "domain-pre-flight/0.1 (+https://github.com/kenimo49/domain-pre-flight)"},
        )
        cdx_resp.raise_for_status()
        rows = cdx_resp.json()
        # First row is the column header.
        data_rows = rows[1:] if rows else []
        snapshot_count = len(data_rows)
        raw["cdx_rows_sampled"] = snapshot_count

        if data_rows:
            has_archive = True
            timestamps = [r[0] for r in data_rows if r and r[0]]
            if timestamps:
                first_dt = _parse_wayback_ts(min(timestamps))
                last_dt = _parse_wayback_ts(max(timestamps))
                if first_dt:
                    first_seen = first_dt.isoformat()
                if last_dt:
                    last_seen = last_dt.isoformat()
                if first_dt and last_dt:
                    age_days = (last_dt - first_dt).days

    except requests.RequestException as e:
        issues.append(f"Wayback CDX query failed: {e.__class__.__name__}")
        raw["cdx_error"] = str(e)

    if has_archive:
        if snapshot_count >= 100:
            notes.append(
                f"{snapshot_count}+ archived snapshots — domain has substantial prior content. "
                "Manually inspect early/late snapshots for topical coherence and abuse signals."
            )
        elif snapshot_count >= 10:
            notes.append(f"{snapshot_count} archived snapshots — moderate prior usage.")
        else:
            notes.append(f"{snapshot_count} archived snapshots — minimal prior usage.")
        if age_days and age_days > 365 * 5:
            notes.append(f"archived span {age_days} days (>5y) — long-running history, audit carefully.")
    else:
        notes.append("no Wayback snapshots — likely never used / very fresh.")

    return HistoryReport(
        domain=domain,
        has_archive=has_archive,
        snapshot_count=snapshot_count,
        first_seen=first_seen,
        last_seen=last_seen,
        age_days=age_days,
        issues=issues,
        notes=notes,
        raw=raw,
    )
