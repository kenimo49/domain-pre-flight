## What this PR does

One paragraph; the imperative form ("add ...", "fix ...", "refactor ...").

## Why

Linked issue or one-line motivation.

## Tests

- [ ] `pytest -q` passes
- [ ] `ruff check src tests scripts` clean
- [ ] `mypy src/domain_pre_flight` clean
- [ ] `bash scripts/smoke.sh --offline` passes
- [ ] Coverage stays at ≥70% for the cli-omitted bundle

## Checklist (delete what doesn't apply)

- [ ] No new runtime dependency added (or, if added, justified in the commit message).
- [ ] If a new check: `score.py` updated with a `_<name>_deductions` function; `cli.py` integrated.
- [ ] If a doc-bearing design choice: ADR added under `docs/decisions/`.
- [ ] CHANGELOG.md updated.
