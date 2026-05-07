# ADR 0003: TLD risk as a JSON bundle with embedded fallback

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

The TLD risk table (~30 entries today) was originally a Python dict literal in `basic.py`. The per-entry data is genuinely refreshable — Spamhaus updates its abuse rankings; new gTLDs get released; some TLDs change registrars and abuse profiles shift. But "one PR per refresh" is a high bar for the kind of contributor (or future cron job) who wants to update the data.

## Decision

Move the table into `src/domain_pre_flight/data/tld_risk.json`. `basic.py` loads the JSON at import time. If the file is missing or corrupt, `basic.py` falls back to an embedded baseline dict — so the package still works in air-gapped environments, partial-build situations, or when someone deletes the data directory.

A separate script `scripts/refresh_tld_risk.py` rewrites the JSON. A monthly GitHub Actions workflow opens an auto-PR with the diff.

## Consequences

- **Easier**: data-only PRs are first-class. Anyone reading the JSON can audit the table; Python knowledge is no longer required to update it.
- **Easier**: future live-feed integrations (Interisle PDFs becoming machine-readable, DAAR opening up, etc.) plug into `_try_fetch_*` functions in the refresh script without touching the runtime path.
- **Harder**: two places to keep consistent — the JSON file and the embedded fallback. The fallback is intentional, not redundant; we accept the duplication.
- **Hard to undo**: trivial. Moving back to a Python dict literal is a one-commit revert.

## Consequences for tests

Tests assert against the JSON-backed `TLD_RISK` dict, not against the embedded fallback. A test for the fallback path (`test_load_falls_back_when_corrupt`) explicitly stubs the loader.

## Alternatives considered

- **TOML / YAML.** Rejected: JSON is the simplest format with stdlib support; no extra dep, easy to diff, easy to lint.
- **Database / SQLite.** Massive overkill for ~30 rows.
- **Live API call at every CLI invocation.** Defeats the offline-first design; air-gapped users would lose the check entirely.
