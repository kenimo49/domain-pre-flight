# ADR 0007: All score weights centralised in `score.py`

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

Initially, `BasicReport.tld_risk_score` carried the raw deduction value across the module boundary into `score.py`. Self-review pointed out that this leaked scoring math into the data layer: `basic.py` was *both* describing the domain (facts) *and* implicitly setting weights (math).

That made it impossible to audit the weights in one place. To answer "what does a `.tk` TLD cost?" you had to read both `basic.py::TLD_RISK` and `score.py::_basic_deductions`.

## Decision

`checks/*.py` modules surface **facts** and **human-readable hints** (`issues`, `notes`). They never carry numeric deduction values across the module boundary.

`score.py` is the single converter from reports to deductions. Every weight in the system lives in one of the `_<name>_deductions(report)` functions or in `_BAND_THRESHOLDS`. Auditing the entire scoring policy = reading `score.py` start-to-finish.

## Consequences

- **Easier**: weight tuning has one editor. ADR 0007 + `docs/agents/tuning-scores.md` → user opens `score.py` → done.
- **Easier**: weights are testable in isolation from the data they apply to.
- **Easier**: a check module that returns no scoring signal (e.g. a future "advisory" check) does not have to fake a zero deduction; it simply has no `_<name>_deductions` function.
- **Harder**: a tiny bit of duplication where a check module's `issues`/`notes` wording mentions severity ("heavily abused") that maps to a deduction in `score.py`. The wording is human-facing; the points are score-facing; both are needed and they are kept in sync via ADRs and tests, not via a shared constant.
- **Hard to undo**: easy to undo for one check, but doing so re-introduces the audit-multiple-files problem we explicitly fixed.

## Alternatives considered

- **A `Severity` enum exported from each check, mapped to points in `score.py`.** Tried in self-review; the enum names ended up duplicating the natural-language `issues` strings without simplifying anything. Rejected.
- **Per-check `score()` methods on the report dataclasses.** Distributes weights across files; same problem we are trying to avoid.
- **Configuration file for weights.** Premature. Hard-coded in `score.py` is fine until there is concrete user demand to change a weight without editing code.
