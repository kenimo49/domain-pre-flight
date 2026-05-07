# Context card: `checks/history.py`

**Path**: `src/domain_pre_flight/checks/history.py`
**Test**: `tests/test_history.py` (when added — currently covered indirectly via score tests)

## Responsibility

Query the Internet Archive Wayback Machine CDX API for past snapshots of the candidate domain. Surface count, first/last archived timestamps, and archive span. No auth, no API key.

## Public API

```python
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

def check_history(domain: str, timeout: int = 10) -> HistoryReport: ...
```

## Dependencies

- `requests` (HTTP)
- `datetime` (timestamp parsing)
- No other in-repo modules.

## Conventions / invariants

- Three CDX queries: `limit=1` ascending (first), `limit=-1` descending (last), `limit=2000` (bounded count).
- `snapshot_count` saturates at 2000; `raw["count_saturated"]` reflects this. See ADR 0004.
- All `requests.RequestException` is caught; failure becomes `issues=["Wayback CDX query failed: ..."]`. Never raises.
- User-Agent header is set on every request.
- `filter=statuscode:200` is applied so only "real" snapshots count; redirects do not.
- Empty / unparseable responses leave `has_archive=False` quietly.

## CDX API quick reference

- Base: `https://web.archive.org/cdx/search/cdx`
- Output: `output=json` returns `[[header_row], [data_row], ...]`. The first row is column names.
- Negative `limit` gives the last N rows in reverse chronological order.

## Common edits

| Change                                | Touch                                |
| ------------------------------------- | ------------------------------------ |
| Increase / decrease count budget      | `COUNT_LIMIT` constant               |
| Tune timeout                          | `DEFAULT_TIMEOUT` constant           |
| Add a new CDX field to surface        | Extend `_cdx_query` and the dataclass |

## Anti-patterns specific to this module

- Pulling all rows just to compute summary stats. We deliberately bound the count.
- Logging snapshot URLs to disk. The module is read-only on archive.org.
- Treating an HTTP error as "no archive" — that is `lookup_failed`, distinct from `has_archive=False`.
