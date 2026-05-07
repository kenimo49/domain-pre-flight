# ADR 0002: `Band` as `(str, Enum)` rather than `StrEnum`

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

The verdict band (`GREEN` / `YELLOW` / `ORANGE` / `RED`) needs to be:

- comparable to a string (so existing dict lookups like `EXIT_CODES[band]` work)
- serialisable to JSON cleanly
- iterable for tests
- readable in tracebacks

`enum.StrEnum` was added in Python 3.11. Using it would be the natural fit, but the project's `requires-python = ">=3.10"` includes 3.10 in the CI matrix.

## Decision

Use `class Band(str, Enum)` instead of `class Band(StrEnum)`. Functionally identical for our use case (comparison to plain strings, JSON-serialisable via `.value`, iterable), works on Python 3.10.

## Consequences

- **Easier**: keeps the 3.10 floor without a `backports.strenum` dependency or version-conditional import.
- **Harder**: very minor cosmetic drift — `StrEnum` is the more "modern" idiom and a Python-3.11+-only project would prefer it.
- **Hard to undo**: trivial. Switching back is a one-line change once the 3.10 floor is dropped.

## Alternatives considered

- **`StrEnum`.** Rejected for now: would either require dropping 3.10 or introducing a backport dependency.
- **Plain string constants (`GREEN = "GREEN"` at module scope).** Rejected: lose the type safety, the iterability, and the explicit set of allowed values that the enum gives us (and that has already caught a typo in code review).
