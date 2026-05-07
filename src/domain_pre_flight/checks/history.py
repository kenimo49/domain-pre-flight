"""Past-content history checks via the Internet Archive Wayback Machine CDX API.

Three small queries (first + last + bounded count) instead of one large dump.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests

WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
DEFAULT_TIMEOUT = 10
USER_AGENT = "domain-pre-flight/0.1 (+https://github.com/kenimo49/domain-pre-flight)"

# Bounded count keeps payload modest while still covering the >=100 and
# >=1000 scoring thresholds; anything beyond 2000 is treated as saturated.
COUNT_LIMIT = 2000


@dataclass
class HistoryReport:
    domain: str
    has_archive: bool = False
    snapshot_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    age_days: int | None = None
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _parse_wayback_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y%m%d%H%M%S")
    except (ValueError, TypeError):
        return None


def _cdx_query(session: requests.Session, params: dict[str, str | int], timeout: int) -> Any:
    resp = session.get(WAYBACK_CDX, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.json()


def check_history(domain: str, timeout: int = DEFAULT_TIMEOUT) -> HistoryReport:
    domain = domain.strip().lower().rstrip(".")
    report = HistoryReport(domain=domain)
    session = requests.Session()
    base = {"url": domain, "output": "json", "filter": "statuscode:200"}

    try:
        first_rows = _cdx_query(session, {**base, "fl": "timestamp", "limit": 1}, timeout)
        last_rows = _cdx_query(session, {**base, "fl": "timestamp", "limit": -1}, timeout)
        first_data = first_rows[1:] if first_rows else []
        last_data = last_rows[1:] if last_rows else []

        if first_data and last_data:
            report.has_archive = True
            first_dt = _parse_wayback_ts(first_data[0][0])
            last_dt = _parse_wayback_ts(last_data[0][0])
            if first_dt:
                report.first_seen = first_dt.isoformat()
            if last_dt:
                report.last_seen = last_dt.isoformat()
            if first_dt and last_dt:
                report.age_days = (last_dt - first_dt).days

            count_rows = _cdx_query(
                session, {**base, "fl": "timestamp", "limit": COUNT_LIMIT}, timeout
            )
            report.snapshot_count = max(0, len(count_rows) - 1) if count_rows else 0
            report.raw["count_saturated"] = report.snapshot_count >= COUNT_LIMIT

    except requests.RequestException as e:
        report.issues.append(f"Wayback CDX query failed: {e.__class__.__name__}")
        report.raw["cdx_error"] = str(e)
        return report

    if report.has_archive:
        if report.snapshot_count >= 1000:
            report.notes.append(
                f"{report.snapshot_count}+ archived snapshots — substantial prior content. "
                "Manually inspect early/late snapshots for topical coherence and abuse signals."
            )
        elif report.snapshot_count >= 100:
            report.notes.append(f"{report.snapshot_count} archived snapshots — moderate prior usage.")
        else:
            report.notes.append(f"{report.snapshot_count} archived snapshots — minimal prior usage.")
        if report.age_days and report.age_days > 365 * 5:
            report.notes.append(
                f"archived span {report.age_days} days (>5y) — long-running history, audit carefully."
            )
    else:
        report.notes.append("no Wayback snapshots — likely never used / very fresh.")

    return report
