# ADR 0005: Bot-walled platforms return `unknown`, not `available`

- **Status**: Accepted
- **Date**: 2026-05-08

## Context

`dpf handles` reports same-name availability across GitHub, npm, PyPI, Twitter/X, and Instagram. GitHub / npm / PyPI have public APIs that distinguish 200 from 404 cleanly. Twitter and Instagram do not — both aggressively challenge anonymous requests, return 200 with a "log in to see this" page, or return 302 to a login wall. There is no honest way to interpret those as "available" or "taken."

## Decision

For Twitter and Instagram:

- HTTP 404 → `available` (this is unambiguous; the platform is saying "no such handle")
- Anything else → `unknown` with `detail = "bot protection — verify in browser"`

Never report `available` for these platforms based on a 200, 302, or 403. The user is told explicitly that the answer is unknown and what to do (verify in a browser).

## Consequences

- **Easier**: the user is never misled. A "go register that name, the handle is free" recommendation is never made on the basis of a fake-200 from Twitter.
- **Harder**: `dpf handles` output has more `unknown` entries than feels satisfying. We accept this — it is the honest answer.
- **Hard to undo**: trivial; easy to change if Twitter ever ships a real availability API.

## Consequences for adjacent decisions

This is also why **adding a new platform with similar bot protection should not happen** (TikTok, Discord, Telegram). If the platform's most common response is `unknown`, adding it just dilutes the signal of the other platforms. See `docs/agents/adding-platforms.md`.

## Alternatives considered

- **Web-scrape the actual page and parse for an "Account suspended" / "doesn't exist" string.** Brittle, breaks when the platform changes its template, and gets us into ToS-questionable territory.
- **Use a paid API like Sherlock or namechk-as-a-service.** Out of scope; the project keeps its public API surface free and self-contained.
- **Just remove Twitter/Instagram from the platform list.** Considered. Kept them because the 404 case is still a real signal, and the `unknown` text serves as a useful prompt to the user.
