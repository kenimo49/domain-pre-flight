# Context card: `checks/handles.py`

**Path**: `src/domain_pre_flight/checks/handles.py`
**Test**: `tests/test_handles.py`

## Responsibility

Same-name availability check across developer platforms and social networks. Parallel HTTP fan-out, distinguishing `taken` / `available` / `unknown`.

## Public API

```python
HandleStatus = Literal["taken", "available", "unknown"]

@dataclass
class HandleResult:
    platform: str
    status: HandleStatus
    detail: str = ""

@dataclass
class HandleReport:
    domain: str
    sld: str
    results: list[HandleResult]
    notes: list[str]

PLATFORM_CHECKS: dict[str, Callable[[str, int], HandleResult]] = {
    "github": check_github,
    "npm": check_npm,
    "pypi": check_pypi,
    "twitter": check_twitter,
    "instagram": check_instagram,
}

def check_handles(
    domain: str,
    *,
    platforms: list[str] | None = None,
    timeout: int = 6,
    max_workers: int = 5,
) -> HandleReport: ...
```

## Dependencies

- `requests` (HTTP via the module-internal `_request` helper)
- `concurrent.futures.ThreadPoolExecutor` (parallel)
- `from .basic import parse_domain` (delayed import to avoid cycles)

## Conventions / invariants

- All HTTP goes through `_request(method, url, timeout)` for consistent UA and timeout.
- Bot-walled platforms (Twitter, Instagram) return `unknown` for any non-404. See ADR 0005.
- 403 / 429 → always `unknown` with rate-limit detail.
- Transport errors → `unknown` with `"transport error"` detail.
- `PLATFORM_CHECKS` is the registry; `check_handles` reads it. Adding a platform = one entry + one function.

## Pattern for a new platform

```python
def check_<platform>(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("GET", f"https://api.<platform>/users/{name}", timeout)
    if resp is None:
        return HandleResult("<platform>", "unknown", "transport error")
    if resp.status_code == 200:
        return HandleResult("<platform>", "taken")
    if resp.status_code == 404:
        return HandleResult("<platform>", "available")
    if resp.status_code in (403, 429):
        return HandleResult("<platform>", "unknown", "rate-limited")
    return HandleResult("<platform>", "unknown", f"http {resp.status_code}")
```

Then add `"<platform>": check_<platform>` to `PLATFORM_CHECKS`.

## Common edits

| Change                              | Touch                                 |
| ----------------------------------- | ------------------------------------- |
| Add a platform                      | New `check_<platform>` + `PLATFORM_CHECKS` entry + tests |
| Tune timeout / concurrency          | `DEFAULT_TIMEOUT` / `max_workers` arg |
| Change User-Agent                   | `USER_AGENT` constant                 |

## Anti-patterns specific to this module

- Adding a platform that returns 200 for both taken and not-taken without a body distinction. See ADR 0005 — that platform should not be added.
- Reporting `available` on any 2xx / 3xx. Only 404 maps to `available`.
- Hard-coding the User-Agent inline.
