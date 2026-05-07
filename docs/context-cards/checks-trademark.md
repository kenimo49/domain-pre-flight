# Context card: `checks/trademark.py`

**Path**: `src/domain_pre_flight/checks/trademark.py`
**Test**: `tests/test_trademark.py`

## Responsibility

Query trademark registries for marks similar to the SLD across US (USPTO), EU (EUIPO), and JP (J-PlatPat). Surface candidates and a deeplink for manual verification. **Flags candidates, never legal opinions.**

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

- Three jurisdictions registered in `_QUERIES`:
  - `us` — `_query_uspto` — live GET against `tmsearch.uspto.gov/api/search/case`
  - `eu` — `_query_euipo` — live POST against `tmdn.org/tmview/api/search/results`
  - `jp` — `_query_jplatpat` — `not_supported`, returns deeplink only (no public API)
- Every `JurisdictionResult` carries a `deeplink` even when the query succeeded — it serves as the "verify manually" link.
- `lookup_failed` status indicates an HTTP error or unrecognised response shape. The user is told and pointed at the deeplink.
- `not_supported` status indicates the registry has no public query path. Currently only J-PlatPat.

## Conventions for response parsing

- USPTO and EUIPO both use varying response shapes; the parser tolerates `_source` wrappers, missing fields, and uppercase/lowercase status strings.
- Empty result list with HTTP 200 is `status="ok"` and `matches=[]`. That is meaningfully different from `lookup_failed`.

## Common edits

| Change                                    | Touch                                 |
| ----------------------------------------- | ------------------------------------- |
| Add a jurisdiction                        | New `_query_<code>` + entry in `_QUERIES` + tests + docs |
| Tune similarity heuristics                | `similarity` field is currently exact-vs-similar based on `mark.lower() == name.lower()`; tighten as needed |
| Add API key support for premium endpoints | Add an env-var lookup inside `_query_<code>` and document in README |

## Anti-patterns specific to this module

- Treating "no matches found" as `lookup_failed`. They are distinct.
- Surfacing legal opinions in `issues`. The wording always says "candidates", "consult counsel", etc. See ADR 0006 / README.
- Removing the deeplink from a `lookup_failed` result. The deeplink is the user's escape hatch.
