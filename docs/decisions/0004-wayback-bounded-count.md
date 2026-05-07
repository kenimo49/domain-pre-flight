# ADR 0004: Wayback queries — three small calls, count capped at 2000

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

The history check originally pulled `limit=5000` rows from Wayback CDX in a single call, just to derive `(count, first_seen, last_seen)`. For popular domains that produced a multi-megabyte JSON response. Self-review flagged the wastefulness — both for archive.org (a free public service we should be polite to) and for the user (slow first run, big memory blip).

The scoring rules need to distinguish:

- 0 snapshots
- some snapshots (<100)
- moderate (≥100)
- substantial (≥1000)

So the count signal only needs to be accurate enough to bucket into those four bands.

## Decision

Use three small CDX calls instead:

- `limit=1` ascending → first archived timestamp
- `limit=-1` descending → last archived timestamp
- `limit=2000` → bounded count; treat anything ≥2000 as saturated

Total payload: ~3 small responses instead of one 5,000-row dump. The count is exact up to 2000 and saturated above that — which is fine because 2000 is already past the ≥1000 threshold and the score bucket is the same.

## Consequences

- **Easier**: friendlier to archive.org; faster first invocation; smaller memory footprint.
- **Easier**: the saturation flag (`raw["count_saturated"]`) lets future tuning know when the count is bounded.
- **Harder**: three round trips instead of one. For a single-domain CLI invocation this does not matter; if someone bulk-runs `dpf history` over thousands of domains, it would. We accept that — bulk usage is not the design centre.
- **Hard to undo**: trivial revert if the upstream API changes.

## Alternatives considered

- **`showNumPages=true` for an exact count.** The Wayback CDX docs describe this but the response shape is poorly documented and varies by domain; depending on it without a strong test signal felt brittle. Revisit if we ever need exact counts beyond 2000.
- **`fastLatest=true` / similar shortcut params.** Tried, did not produce a stable result across domains. Rejected.
- **Drop the count entirely, use only first/last.** Rejected: scoring depends on the magnitude bucket, not the existence-or-not signal alone.
