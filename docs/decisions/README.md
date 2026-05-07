# Architecture Decision Records

Each file is a short ADR (Architecture Decision Record) capturing **why** a non-obvious design choice was made. Numbered chronologically.

ADRs are the cheapest way to keep a future contributor (human or AI) from undoing a decision that was made for a real reason that didn't make it into the code comments.

## Index

| ADR | Title                                                          | Status   |
| --- | -------------------------------------------------------------- | -------- |
| [0001](0001-tldextract-for-psl-parsing.md) | `tldextract` for PSL-aware SLD/TLD parsing | Accepted |
| [0002](0002-band-as-str-enum-not-strenum.md) | `Band` as `(str, Enum)` rather than `StrEnum` | Accepted |
| [0003](0003-tld-risk-as-json-bundle.md) | TLD risk as a JSON bundle with embedded fallback | Accepted |
| [0004](0004-wayback-bounded-count.md) | Wayback queries: 3 small calls, count capped at 2000 | Accepted |
| [0005](0005-bot-walled-platforms-return-unknown.md) | Bot-walled platforms return `unknown`, not `available` | Accepted |
| [0006](0006-trademark-default-off.md) | Trademark check defaults to OFF (opt-in)               | Accepted |
| [0007](0007-score-weights-centralised.md) | All score weights centralised in `score.py`           | Accepted |
| [0008](0008-llmo-experimental-marker.md) | LLMO check is permanently marked experimental         | Accepted |

## Writing a new ADR

When you make a design choice that future readers might want to undo, write a short ADR:

```markdown
# ADR NNNN: <title>

- **Status**: Accepted | Superseded by ADR NNNN
- **Date**: YYYY-MM-DD

## Context
What problem are we solving? What constraints are in play?

## Decision
What did we choose to do?

## Consequences
What does this make easier? What does this make harder? What is now hard to undo?

## Alternatives considered
What did we look at and rule out, and why?
```

Keep ADRs under 1 page. They are cheap to add but expensive to maintain at length.
