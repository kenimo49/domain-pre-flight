# ADR 0009: Trademark check is deeplink-only

- **Status**: Accepted (supersedes the live-query parts of ADR 0006)
- **Date**: 2026-05-08

## Context

ADR 0006 documented the design "trademark check defaults OFF, opt-in via `--check-trademark`." It also assumed the underlying queries against USPTO and EUIPO would actually work. They do not.

Field reality, observed when the v0.7 release was used to pre-flight a real candidate-domain shortlist:

- `tmsearch.uspto.gov` is a Single-Page Application. The search HTTP API used by its frontend is **not documented**, requires CORS / token handling, and the URL path the SPA hits is built dynamically inside the JS bundle. The endpoint we were calling (`/api/search/case`) returns CloudFront 404 for direct anonymous requests.
- `tmdn.org/tmview/` (EUIPO) is similarly a SPA. Its backend is reachable but rejects the payload shape we send (and the documented payload shape varies by client / version).
- `tsdr.uspto.gov` is a status-by-serial-number API; it cannot be used for free-text search.
- J-PlatPat (JP) has no public API at all — already documented as `not_supported`.

In practice, every `lookup_failed` we surfaced was caused by our endpoint guesses being wrong, not by the registries being down. Users got `lookup_failed` rows and assumed our tool was flaky; the underlying truth was that the queries never had a chance.

## Decision

Stop attempting live queries. Every jurisdiction (us / eu / jp) now resolves synchronously to:

- `status = "not_supported"`
- a `detail` string explaining there is no public, documented search API
- a pre-filled `deeplink` to the official search UI for the SLD

The user clicks the deeplink and verifies in a browser. The tool does not pretend to have run a search.

## Consequences

- **Easier**: `dpf trademark` and `dpf check --check-trademark` always succeed now. No flaky network calls. No false `lookup_failed` rows.
- **Easier**: removes a maintenance burden — we no longer have to chase USPTO / EUIPO SPA changes that would silently break our queries.
- **Easier**: `requests` and `urllib3.Retry` plumbing in the trademark module disappear; the module shrinks substantially.
- **Harder**: no automatic flag of trademark conflicts. The user must manually verify. We accept this — it matches how trademark verification actually happens in the real world (legal counsel reads the registry result; tools surface candidates).
- **Harder**: scoring no longer deducts points for trademark hits, because there are no machine-detected hits. The score model drops one signal. We accept this — a deduction based on a fake `lookup_failed` was already meaningless.

## Backward compatibility

The public API (`check_trademark`, `TrademarkReport`, `JurisdictionResult`, `TrademarkMatch`, `Similarity`, `JurisdictionStatus`) is unchanged. The CLI flag (`--check-trademark`) and subcommand (`dpf trademark`) keep their names. The `--trademark-jurisdictions` flag still accepts `us,eu,jp` subsets.

`timeout` and `max_workers` arguments to `check_trademark` are kept for signature compatibility but unused.

## Future revisit

If, at some point, USPTO or EUIPO publishes a stable, documented, no-auth search REST API, re-introduce the live query for that jurisdiction. Keep the deeplink as the fallback for the others. The data structures already accommodate `status="ok"` with populated `matches`, so the code path is preserved.

## Alternatives considered

- **Reverse-engineer the SPA bundles** to find the real endpoints. Rejected: the endpoints change without notice, are not in the public ToS, and using them would be brittle. Even if we got it working, we would be one frontend deploy away from breaking again.
- **Bundle a Selenium / Playwright browser** to drive the SPA UI. Rejected: enormous dependency surface for a v0.x tool, ToS-questionable, and slow.
- **Use a paid trademark search API** (Markify, TM Cloud, etc.). Rejected: out of scope for the project's "free signals first" design.
- **Just remove the trademark check entirely.** Rejected: the deeplinks are a real, useful UX — they pre-fill the search UI with the SLD, saving the user a click.
