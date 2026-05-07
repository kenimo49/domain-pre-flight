# ADR 0008: LLMO check is permanently marked experimental

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

The LLMO fitness check (pronunciation / memorability) is the most subjective signal in the suite. It scores SLDs along four heuristic axes (cluster, vowel ratio, length, repeats), each tuned by judgement rather than empirical study. The thresholds (e.g. "vowel ratio sweet spot 0.30-0.55") are educated guesses, not measurements.

A normal "v0.x → v1.0" trajectory would imply that, eventually, this check graduates out of "experimental" and into the same trust tier as the structural / Wayback / typosquat checks. We don't think that should happen.

## Decision

The LLMO check is *permanently* marked experimental in CLI output (the table title says `(experimental)`) and in the README / usage guide. The marker is not a "we'll fix this later" sign; it is a "this signal is structurally less precise than the others" sign.

## Consequences

- **Easier**: future contributors do not feel pressure to "remove the experimental marker" before tuning the heuristics further. The marker stays; tuning happens on top of it.
- **Easier**: users see the label and treat the LLMO score as one input among many, not a verdict-driver.
- **Easier**: when we (eventually) add a CMU-pronunciation-dictionary integration, the experimental marker stays — even with the dictionary, the heuristics are still English-leaning and judgement-driven.
- **Harder**: the report can never claim the same authority as the trademark or typosquat checks. We accept this — it is the honest framing.
- **Hard to undo**: trivial mechanically (delete the word); but undoing means re-introducing a subtle credibility problem we explicitly avoided.

## Alternatives considered

- **Make LLMO opt-in (default-off) instead of experimental-but-on.** Considered; rejected because the check is offline and cheap, so default-on costs nothing, and the signal is occasionally useful.
- **Separate "experimental" badge per axis (cluster experimental, length not).** Over-engineered for the actual precision differences.
- **Drop the LLMO check entirely.** The book chapter that motivated it (LLMO authority in `domain-hunter-engineer-collab` ch06) is real and the signal is occasionally useful; keep it, label it correctly.
