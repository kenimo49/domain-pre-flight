# Context card: `checks/trademark.py`

**Path**: `src/domain_pre_flight/checks/trademark.py`
**Test**: `tests/test_trademark.py`

## Responsibility

Surface a deeplink to each jurisdiction's official trademark search UI (US: USPTO; EU: EUIPO TMview; JP: J-PlatPat) so the user can manually verify. **No live API queries** — see [ADR 0009](../decisions/0009-trademark-deeplink-only.md) for the rationale (none of the three registries publishes a stable, documented, no-auth search API). Flags candidates, never legal opinions.

## Public API

```python
JurisdictionStatus = Literal["ok", "lookup_failed", "not_supported"]

@dataclass
class TrademarkMatch:
    mark: str
    owner: str
    status_text: str
    serial: str
    classes: list[str]
    similarity: Literal["exact", "similar"]

@dataclass
class JurisdictionResult:
    jurisdiction: str
    status: JurisdictionStatus
    detail: str
    matches: list[TrademarkMatch]
    deeplink: str

@dataclass
class TrademarkReport:
    domain: str
    sld: str
    jurisdictions: list[JurisdictionResult]
    issues: list[str]
    notes: list[str]
    @property
    def has_exact_match(self) -> bool: ...

def check_trademark(
    domain: str,
    *,
    jurisdictions: list[str] | None = None,  # default ["us", "eu", "jp"]
    timeout: int = 12,
    max_workers: int = 3,
) -> TrademarkReport: ...
```

## Dependencies

- `requests` + `Session` (HTTP)
- `concurrent.futures.ThreadPoolExecutor` (parallel)
- `from .basic import parse_domain` (delayed import)

## Conventions / invariants

- Three jurisdictions registered in `_DEEPLINK_TEMPLATES`:
  - `us` → `tmsearch.uspto.gov/search/search-information?q=<sld>`
  - `eu` → `tmdn.org/tmview/#/tmview/results?text=<sld>`
  - `jp` → `j-platpat.inpit.go.jp/t0100?term=<sld>`
- Every `JurisdictionResult` is `status="not_supported"` with a populated `deeplink`. The data structures still accommodate `status="ok"` + populated `matches` so a future live-query restoration is plug-in.
- The function takes `timeout` and `max_workers` for backward compatibility — both unused under deeplink-only mode.
- `_deeplink_for(jurisdiction, sld)` is the single helper; the SLD is URL-encoded via `quote_plus` before being substituted into the template.

## Common edits

| Change                                    | Touch                                          |
| ----------------------------------------- | ---------------------------------------------- |
| Add a jurisdiction                        | Add an entry to `_DEEPLINK_TEMPLATES` (jurisdiction → (template, detail)) + tests + docs |
| Update a deeplink URL                     | The relevant entry in `_DEEPLINK_TEMPLATES`    |
| Restore live querying for a jurisdiction  | Re-introduce the `_query_<code>` function, add to a `_QUERIES` registry, fan out via `ThreadPoolExecutor`. Update ADR 0009 accordingly. |

## Anti-patterns specific to this module

- Speculatively guessing API endpoints again. ADR 0009 explicitly rejects this — only restore live querying when a registry publishes a documented, stable, no-auth search API.
- Surfacing legal opinions in `issues`. The wording always says "candidates", "consult counsel", etc.
- Removing the top-level `notes` entry that points the user at the deeplinks. That note is the UX contract.
