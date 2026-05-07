# Context card: `checks/score.py`

**Path**: `src/domain_pre_flight/checks/score.py`
**Test**: `tests/test_score.py`

## Responsibility

The single converter from check reports to a numeric verdict. **Every score weight in the system lives here.** See ADR 0007.

## Public API

```python
class Band(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"

EXIT_CODES: dict[Band, int] = {Band.GREEN: 0, Band.YELLOW: 0, Band.ORANGE: 1, Band.RED: 2}

@dataclass
class Verdict:
    score: int
    band: Band
    summary: str
    deductions: list[tuple[str, int]]

def aggregate(
    basic: BasicReport,
    history: HistoryReport | None = None,
    typosquat: TyposquatReport | None = None,
    trademark: TrademarkReport | None = None,
    semantics: SemanticsReport | None = None,
    llmo: LlmoReport | None = None,
) -> Verdict: ...
```

## Dependencies

All seven check modules. `score.py` is the *integration* layer.

## Conventions / invariants

- One private function per check: `_<name>_deductions(report) -> list[tuple[str, int]]`.
- `aggregate` calls each `_*_deductions` in turn and concatenates. Sum of points is capped at 100; score = `100 - total`.
- `_band_for(score)` walks `_BAND_THRESHOLDS` (descending) and returns the first match.
- `_SUMMARIES[band]` is the user-facing summary string per band.
- `EXIT_CODES[band]` is the CLI exit code per band.

## Adding a new check's scoring

```python
from .<newcheck> import <NewCheck>Report

def _<newcheck>_deductions(report: <NewCheck>Report) -> list[tuple[str, int]]:
    if not report.matches:        # or whatever indicates "nothing to flag"
        return []
    return [("...", N)]

def aggregate(
    basic: BasicReport,
    history: HistoryReport | None = None,
    typosquat: TyposquatReport | None = None,
    trademark: TrademarkReport | None = None,
    semantics: SemanticsReport | None = None,
    llmo: LlmoReport | None = None,
    <newcheck>: <NewCheck>Report | None = None,    # add this
) -> Verdict:
    # ...
    if <newcheck> is not None:
        deductions.extend(_<newcheck>_deductions(<newcheck>))
```

## Score budget reference (current)

| Source             | Heaviest deduction     | Lightest deduction  |
| ------------------ | ---------------------- | ------------------- |
| `_basic`           | invalid syntax (-100)  | various small (-5)  |
| `_history`         | -25 (>1000 snapshots)  | -10 (>=100)         |
| `_typosquat`       | -60 (exact)            | -15 (bigram)        |
| `_trademark`       | -50 (exact match)      | -10 (similar)       |
| `_semantics`       | -70 (severe exact)     | -30 (severe substr) |
| `_llmo`            | -10 (poor)             | -3 (ok)             |

Total cap is 100. Any single high-stakes signal can take the verdict to RED on its own (intended).

## Common edits

| Change                                | Touch                                    |
| ------------------------------------- | ---------------------------------------- |
| Tune a weight                         | The relevant `_<name>_deductions`         |
| Move band thresholds                  | `_BAND_THRESHOLDS` (rare; updates UX)    |
| Change an exit code                   | `EXIT_CODES`                             |
| Add a check-specific exception clause | The relevant `_<name>_deductions`         |

## Anti-patterns specific to this module

- Reading `BasicReport` fields and doing structural validation here. That belongs in `basic.py`. `score.py` only converts facts to deductions.
- Adding a `_<name>_deductions` that returns a deduction even when the report has no signal. Returning `[]` for a clean report is correct.
- Importing CLI state. `score.py` is pure-Python and library-callable.
