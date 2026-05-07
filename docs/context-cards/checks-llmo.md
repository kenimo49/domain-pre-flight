# Context card: `checks/llmo.py`

**Path**: `src/domain_pre_flight/checks/llmo.py`
**Test**: `tests/test_llmo.py`

## Responsibility

Pronunciation / memorability heuristic. Scores the SLD on four offline axes (cluster, vowel, length, repeats), each 0–5; total 0–20. **Permanently marked experimental** — see ADR 0008.

## Public API

```python
@dataclass
class LlmoReport:
    domain: str
    sld: str
    cluster_score: int
    vowel_score: int
    length_score: int
    repeats_score: int
    fitness: int
    band: Literal["excellent", "good", "ok", "poor"]
    issues: list[str]
    notes: list[str]

def check_llmo(domain: str) -> LlmoReport: ...
```

## Dependencies

- None beyond Python stdlib.
- `from .basic import parse_domain` (delayed import).

## Conventions / invariants

- Each axis returns 0–5; total `fitness = sum(axes)`, max 20.
- Band thresholds: `excellent` ≥ 16, `good` ≥ 11, `ok` ≥ 6, `poor` < 6.
- Only `poor` and `ok` produce score deductions in `score.py` (10 and 3 respectively).
- Vowel sweet spot: 0.30–0.55.
- Length sweet spot: 4–9 chars. 3 or 10–12 is mid; 2 or 13–15 is poor; outside that is 0.
- Repeated-character runs of 1 are full marks; 2 acceptable; 3+ penalised.
- All scoring is monotonic — no axis penalises the *absence* of something.

## Constants worth knowing

```python
VOWELS = set("aeiouy")  # y is treated as a vowel for ratio purposes
```

If you change `VOWELS`, update tests; the band thresholds will move silently.

## Common edits

| Change                                | Touch                                    |
| ------------------------------------- | ---------------------------------------- |
| Tune an axis threshold                | The branch in `check_llmo` for that axis |
| Change band cutoffs                   | `_band_for`                              |
| Adjust treat-y-as-vowel               | `VOWELS` constant + tests                |

## Anti-patterns specific to this module

- "Removing the experimental marker" once a tuning round is complete. The marker is a permanent property of the check (ADR 0008), not a "we'll fix this later" flag.
- Adding a 5th axis without a corresponding ADR. The 4-axis design is balanced; expanding it without justification dilutes the signal.
- Using a CMU dictionary lookup unconditionally. Most SLDs are not real English words, so the dictionary lookup misses; if you add one, it must degrade gracefully.
- Letting the score exceed 20. Cap if you change the axis count.
