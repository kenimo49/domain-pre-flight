# Recipe: Tuning score weights and band thresholds

All scoring math is in `src/domain_pre_flight/checks/score.py`. This recipe is for changing what a deduction is worth, not for adding a new check (that's `extending-checks.md`).

## What lives where

- **Per-check deduction values**: inside the `_<name>_deductions(report)` functions. Each returns `[(reason_string, points), ...]`.
- **Score → band mapping**: `_BAND_THRESHOLDS` (descending list of `(threshold, Band)`).
- **Band → exit code mapping**: `EXIT_CODES`.
- **Band → CLI summary string**: `_SUMMARIES`.

If you find yourself reaching for a weight outside this file, the layering is broken; fix the layering instead.

## Tuning weights

The current weights are conservative on purpose. Calibration is ongoing — see the `experimental` warning in the README. Before changing a weight:

1. **Find the failing case.** Which domain caused the verdict you disagree with? Reproduce with `dpf check <domain> --json`.
2. **Read the deduction list.** The JSON `verdict.deductions` array shows every deduction with its current weight. Identify the one driving the verdict in the wrong direction.
3. **Decide which way to move.**
   - Verdict too harsh? Reduce the weight on the deduction.
   - Verdict too lenient? Increase it, *or* add a stricter case in the check module that only fires under tighter conditions.

### Heuristics for picking a weight

- **A signal that almost certainly disqualifies a name** → 50–70 points (e.g. exact trademark match, severe slur exact match).
- **A signal that strongly suggests problems but has false-positive risk** → 25–35 (e.g. typosquat near match, severe slur substring).
- **A signal that is a meaningful note but not a deal-breaker on its own** → 10–20 (e.g. lots of prior Wayback content, similar trademarks in one jurisdiction).
- **A signal that is informational, not actionable on its own** → 0–5 or use `notes` instead of a deduction.

Bias toward **not** deducting if you are unsure. A note that the user reads is much better than a deduction the user has to argue with.

### Example: adjusting the typosquat weight

Suppose a real-world test shows that distance-2 matches are too aggressive and the verdict is dropping legitimate names from GREEN to YELLOW.

Today:

```python
def _typosquat_deductions(report: TyposquatReport) -> list[tuple[str, int]]:
    ...
    if first.kind in {"near", "homoglyph"}:
        return [(f"resembles known brand '{first.brand}' ({first.kind})", 30)]
    ...
```

Change to:

```python
def _typosquat_deductions(report: TyposquatReport) -> list[tuple[str, int]]:
    ...
    if first.kind == "homoglyph":
        return [(f"resembles known brand '{first.brand}' (homoglyph)", 30)]
    if first.kind == "near":
        if first.distance == 1:
            return [(f"resembles known brand '{first.brand}' (distance 1)", 30)]
        return [(f"resembles known brand '{first.brand}' (distance 2)", 15)]
    ...
```

Now distance-2 only deducts 15 instead of 30; distance-1 keeps the strict treatment.

Then update `tests/test_score.py` if any of the existing band assertions move. If they do, that is a real coverage signal — pick a different fixture or accept the new band.

## Tuning band thresholds

`_BAND_THRESHOLDS` defines the score → band map. Bands have downstream impact (exit codes, CLI colour, summary text), so changing thresholds is more invasive than tuning a single deduction.

Don't change band thresholds unless:

- You can demonstrate that 70+ examples cluster wrong on the current 90/70/40 split.
- You have updated `_SUMMARIES` and `EXIT_CODES` to match the new shape.
- You have updated the smoke fixtures in `scripts/smoke.sh` (some of them assert exit codes per band).

Almost always, the right thing to change is a deduction value, not a band threshold.

## Validate

```bash
pytest -q
bash scripts/smoke.sh --offline
```

If smoke fails on a band assertion, that is the test telling you a real domain just changed verdict. Either:

- Accept the new verdict and update the smoke fixture (if the change was intentional and correct).
- Revert the deduction change (if the test fixture is the canonical case you didn't want to break).

Never silently change a smoke fixture to match the new score. If the fixture is wrong, say so in the commit message.

## Anti-patterns

- **Tuning a weight to make a single user's domain pass.** That is a calibration of one. Wait for ≥3 independent cases pulling the same direction before moving the weight.
- **Adding a new band ("LIME" between GREEN and YELLOW).** The 4-band split is a UX simplification, not a precision claim. Resist.
- **Hiding a deduction by setting it to 0.** Either the signal matters and deserves points, or it should be a note, not a zero-point deduction.
