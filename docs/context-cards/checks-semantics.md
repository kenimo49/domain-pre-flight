# Context card: `checks/semantics.py`

**Path**: `src/domain_pre_flight/checks/semantics.py`
**Test**: `tests/test_semantics.py`
**Data**: `src/domain_pre_flight/data/negative_meanings/<lang>.txt`

## Responsibility

Multi-language negative-meaning scan: detect whether the SLD contains or matches a slur, vulgar term, or unfortunate reading in EN / ES / PT / JA / KO / ZH. Pure offline; deterministic.

## Public API

```python
Severity = Literal["severe", "mild"]
SUPPORTED_LANGUAGES = ["en", "es", "pt", "ja", "ko", "zh"]

@dataclass
class SemanticMatch:
    language: str
    term: str
    severity: Severity
    kind: Literal["exact", "substring"]

@dataclass
class SemanticsReport:
    domain: str
    sld: str
    languages: list[str]
    matches: list[SemanticMatch]
    issues: list[str]
    notes: list[str]

def check_semantics(domain: str, languages: list[str] | None = None) -> SemanticsReport: ...
```

## Dependencies

- `importlib.resources` (load lists)
- `from .basic import parse_domain` (delayed import)

## Conventions / invariants

- One file per language at `data/negative_meanings/<lang>.txt`.
- Format: `term[<TAB>severity]`. Severity defaults to `mild`.
- Comments (`#`) and blank lines skipped.
- Only ASCII / romanised forms — the SLD is ASCII, native-script entries cannot match.
- Match modes:
  - `exact`: `sld == term`
  - `substring`: `term in sld`, **only** for terms with `len(term) >= 4` (anti–false-positive guard for short terms like "sex")
- `severe + exact` → issue ("do not register"), heavy deduction in `score.py`
- `severe + substring` → issue ("likely problematic"), medium deduction
- `mild + anything` → note only, no deduction

## Common edits

| Change                                    | Touch                                                  |
| ----------------------------------------- | ------------------------------------------------------ |
| Add a term to an existing language        | `data/negative_meanings/<lang>.txt` (data-only PR + citation) |
| Add a new language                        | New `<lang>.txt` + extend `SUPPORTED_LANGUAGES` + tests + docs |
| Adjust the substring-length guard (4)     | The `len(term) >= 4` line in the loop                  |

## Anti-patterns specific to this module

- Crowd-sourcing terms without citations. The lists are intentionally curated. PRs adding terms must include a source.
- Using regex for matching. Plain `==` and `in` are correct and predictable; regex would invite escaping bugs and locale issues.
- Lowering a `severe` term to `mild` to avoid a false positive in one case. Either the term should not be on the list, or the substring guard should be raised — not the severity.
