# Context card: `checks/basic.py`

**Path**: `src/domain_pre_flight/checks/basic.py`
**Test**: `tests/test_basic.py`, `tests/test_tld_risk_bundle.py`
**Data**: `src/domain_pre_flight/data/tld_risk.json` (loaded at import time, falls back to embedded dict)

## Responsibility

Offline structural validation of a candidate domain: hostname syntax (RFC 1035), length, hyphens, digits, IDN/punycode, SLD/TLD split, and the per-TLD risk *hint* lookup. **No network calls. No scoring math.**

## Public API

```python
def parse_domain(domain: str) -> tuple[str, str]:
    """Return (sld, tld) using PSL via tldextract."""

@dataclass
class BasicReport:
    domain: str
    tld: str
    sld: str
    label_length: int
    hyphens: int
    digits: int
    has_idn: bool
    is_valid_syntax: bool
    issues: list[str]
    notes: list[str]
    @property
    def length(self) -> int: ...

def check_basic(domain: str) -> BasicReport: ...
def tld_risk_for(tld: str) -> int:
    """Lookup risk hint. Unknown TLDs default to 25."""
```

## Dependencies

- `tldextract` (PSL-aware split)
- `re` (label validation)
- `importlib.resources` (load JSON bundle)
- No other in-repo modules.

## Conventions / invariants

- Lowercase + strip + rstrip(".") on every input.
- `is_valid_syntax` checks each label against `LABEL_RE` (RFC 1035).
- `has_idn` is true if any non-ASCII char OR `xn--` substring.
- TLD risk dict is loaded once at module import; corrupt JSON falls back to `_FALLBACK_TLD_RISK` silently. Do **not** add logging on the fallback path — the fallback is intentional.
- The module emits `issues` / `notes` (human strings) but never numeric deduction values. Scoring lives in `score.py`.

## Common edits

| Change                              | Touch                                    |
| ----------------------------------- | ---------------------------------------- |
| Add a new structural check          | Add a block inside `check_basic` that appends to `issues` / `notes` |
| Adjust the TLD risk default (25)    | `tld_risk_for` (one line)                |
| Add a TLD                           | `data/tld_risk.json` (data-only PR)      |
| Tighten label validation            | `LABEL_RE`                               |

## Anti-patterns specific to this module

- Calling the network from a function in this file.
- Adding a numeric deduction value to `BasicReport` for `score.py` to read.
- Adding a TLD list with severity tiers as a new constant; data lives in JSON.
