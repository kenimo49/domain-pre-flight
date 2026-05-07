# ADR 0001: `tldextract` for PSL-aware SLD/TLD parsing

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

The first version shipped a hand-rolled `parse_domain()` that just split on the last dot. That works for `example.com` but produces `("example.co", "jp")` for `example.co.jp` — wrong, because `co.jp` is a single Public Suffix List entry. The TLD risk lookup then ran against `jp` instead of `co.jp`, which by accident happened to give the right risk score, but a multi-label TLD with a different risk profile (`gov.uk`, `co.za`, `com.br`) would have been misclassified.

## Decision

Add `tldextract>=5.1` as a runtime dependency and route all SLD/TLD parsing through it. Disable PSL network refresh at runtime (`tldextract.TLDExtract(suffix_list_urls=())`) so the bundled snapshot is used; that snapshot is good enough for risk-hint purposes.

## Consequences

- **Easier**: every check module gets correct PSL parsing for free; multi-label TLDs work.
- **Harder**: one extra dependency; the package now pulls in `tldextract`, `requests`, and a vendored PSL snapshot.
- **Hard to undo**: any future PSL-aware feature (e.g. registrar-level or eTLD+1 features) would also need this; switching to a different library means re-validating every check.

## Alternatives considered

- **Keep hand-rolled split.** Rejected: documented to mishandle multi-label TLDs, and the bug enshrines itself in tests.
- **`publicsuffixlist` library.** Functionally equivalent, slightly less ergonomic API; `tldextract` is more widely used in the Python ecosystem and the API matches what the rest of the code wants (`subdomain`, `domain`, `suffix`).
- **Bundle our own PSL snapshot manually.** Reinvents `tldextract`; not worth the maintenance burden.
