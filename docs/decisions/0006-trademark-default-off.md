# ADR 0006: Trademark check defaults to OFF

- **Status**: Partially superseded by [ADR 0009](0009-trademark-deeplink-only.md) — the live-query part of this decision was removed; the "default OFF, opt-in" part still applies.
- **Date**: 2026-05-08

## Context

`dpf check` runs every signal-producing check by default. The trademark check is the one exception — it is opt-in via `--check-trademark`. Two pressures argued for making it default-on (it is the highest-stakes check; missing a trademark conflict is the worst failure mode the tool tries to prevent) and several against.

## Decision

Trademark stays default-off. To enable it, pass `--check-trademark` (and optionally `--trademark-jurisdictions us,eu,jp`).

## Consequences

- **Easier**: `dpf check` stays fast (sub-2-second) and friendly to bulk-pipeline use. Two slow public APIs (USPTO, EUIPO) are not hit unless the user opts in.
- **Easier**: the legal disclaimer ("flags candidates, not legal opinions") is exposed to the user at the moment they explicitly choose to run trademark queries — they cannot stumble into it.
- **Easier**: USPTO / EUIPO public APIs occasionally rate-limit; making them default-on would make CI flaky for downstream consumers of `dpf check`.
- **Harder**: a user who runs `dpf check` and feels safe might miss a trademark conflict. We accept this and document it loudly: the README, the usage guide, and the trademark-check help text all surface the disclaimer and the opt-in flag.
- **Hard to undo**: easy revert, but doing so would re-introduce the API dependency surface for default-path users.

## What we did instead

- **Document the gap.** README and usage guide both call out trademark as opt-in.
- **Make opt-in cheap.** A single flag, no config files, no API keys.
- **Show a deeplink even when query fails.** The report always carries a `deeplink` field per jurisdiction so the user can verify manually if our query failed (or if J-PlatPat — which has no public API — is the relevant jurisdiction).

## Alternatives considered

- **Default-on with a graceful timeout.** Tried in design; the resulting `dpf check` invocation took ~10 seconds and produced flaky tests. Not worth it.
- **Default-on with `--no-trademark` flag.** Same UX problem, opposite default. Picked the more conservative direction.
- **Cache trademark results locally.** Out of scope for v0.x; would help bulk usage but adds a moving part.
