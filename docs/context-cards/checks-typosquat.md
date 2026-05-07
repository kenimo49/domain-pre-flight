# Context card: `checks/typosquat.py`

**Path**: `src/domain_pre_flight/checks/typosquat.py`
**Test**: `tests/test_typosquat.py`
**Data**: `src/domain_pre_flight/data/known_brands.txt`

## Responsibility

Detect when the candidate SLD is identical to or confusingly similar to a known brand stem. Pure offline; deterministic.

## Public API

```python
@dataclass
class BrandMatch:
    brand: str
    distance: int
    kind: Literal["exact", "near", "possible", "homoglyph", "bigram"]

@dataclass
class TyposquatReport:
    domain: str
    sld: str
    matches: list[BrandMatch]
    issues: list[str]
    notes: list[str]
    @property
    def worst_kind(self) -> str | None: ...

def load_brands() -> list[str]: ...
def check_typosquat(domain: str, brands: list[str] | None = None) -> TyposquatReport: ...
```

## Dependencies

- `Levenshtein` (fast C edit distance)
- `importlib.resources` (load brand list)
- `from .basic import parse_domain` (delayed import)

## Conventions / invariants

- Brand list is loaded from `data/known_brands.txt` lazily. Comments (`#`) and blank lines skipped.
- Tests pass `brands=[...]` explicitly to isolate from the bundled data.
- SLDs shorter than 4 characters are exempt from similarity matching to avoid "distance 2 to 'lg'" false positives. Exact match still applies.
- Brands shorter than 4 characters are skipped during similarity matching for the same reason.
- Match kinds, in priority order:
  - `exact` — `sld == brand`
  - `homoglyph` — de-substituted `sld_homoglyph` within distance 1 of brand (preferred over near, since this *is* the typosquat signal)
  - `near` — Levenshtein 1–2
  - `possible` — Levenshtein 3 (note only, no deduction)
  - `bigram` — same bigram set, similar length, different ordering
- `HOMOGLYPHS` map covers 0→o, 1→l, 5→s, $→s, @→a, rn→m, vv→w. Add new ones if you see a clear pattern in the wild.

## Thresholds

```python
EXACT_MATCH = 0
NEAR_DISTANCE = 2          # 1 or 2 = high-risk
POSSIBLE_DISTANCE = 3      # 3 = note only
```

These are not gospel; tuning them changes false-positive / false-negative balance. Rerun smoke after any change.

## Common edits

| Change                                      | Touch                                |
| ------------------------------------------- | ------------------------------------ |
| Add brands                                  | `data/known_brands.txt` (data-only PR) |
| Add a homoglyph substitution                | `HOMOGLYPHS` dict                    |
| Tighten / loosen near-distance              | `NEAR_DISTANCE` constant             |
| Adjust short-SLD exemption                  | `similarity_eligible = len(sld) >= 4` line |

## Anti-patterns specific to this module

- Returning numeric scoring weights from this module. See ADR 0007 — weights live in `score.py`.
- Comparing the SLD against the brand list without first running `parse_domain`. Subdomains would slip through.
- Reading `data/known_brands.txt` outside of `load_brands()`. There should be exactly one loader.
