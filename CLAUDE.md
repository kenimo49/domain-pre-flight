# CLAUDE.md — domain-pre-flight

> **For AI coding agents (Claude Code, Cursor, etc.):** read this file first. It is the highest-signal map of the repository. The other files under `docs/` go deeper as needed.

## What this repo is

A Python CLI that runs **pre-flight checks before someone registers a domain for a new site or app**. It is *not* a domain-investing or aftermarket-trading tool. It answers one question: *"is this name safe to register?"*

The companion is the (currently unpublished) Japanese-language Kindle book `domain-hunter-engineer-collab` by Ken Imoto; this tool is the runnable subset of chapters 1–6 of that book ("evaluation / authority").

## How to use this map

Tasks usually land in one of four shapes. Jump to the right doc:

| If your task is…                          | Start with                                         |
| ----------------------------------------- | -------------------------------------------------- |
| "Run / use the CLI"                       | [`docs/guide/usage.md`](docs/guide/usage.md)       |
| "Understand how the pieces fit together"  | [`docs/architecture.md`](docs/architecture.md)     |
| "Add a new check / extend a check"        | [`docs/agents/extending-checks.md`](docs/agents/extending-checks.md) |
| "Edit data only (brand list, word lists)" | [`docs/agents/data-updates.md`](docs/agents/data-updates.md) |
| "Understand *why* a design choice exists" | [`docs/decisions/`](docs/decisions/)               |
| "Get the smallest possible context for one module" | [`docs/context-cards/`](docs/context-cards/) |

If you only have time for one more file, read [`docs/architecture.md`](docs/architecture.md). It has the layer diagram and the data flow.

## Quick orientation (60 seconds)

```
src/domain_pre_flight/
├── cli.py                  # Click entry point — owns all subcommands and rendering
├── checks/                 # one module per check; each owns its own dataclass report
│   ├── basic.py            # offline structural checks + TLD risk lookup
│   ├── history.py          # Wayback Machine (3 cheap CDX queries)
│   ├── handles.py          # GitHub / npm / PyPI / X / Instagram (parallel)
│   ├── typosquat.py        # Levenshtein + homoglyph + bigram vs known_brands
│   ├── trademark.py        # deeplink-only for USPTO / EUIPO / J-PlatPat (ADR 0009)
│   ├── semantics.py        # multi-language negative-meaning scan
│   └── llmo.py             # pronunciation / memorability heuristic (experimental)
├── checks/score.py         # aggregates check reports into a single Verdict
└── data/                   # bundled, refreshable data
    ├── tld_risk.json       # editable; refreshed by scripts/refresh_tld_risk.py
    ├── known_brands.txt    # one stem per line; comments with #
    └── negative_meanings/  # one file per language: term[\tseverity]

scripts/
├── refresh_tld_risk.py     # refreshes data/tld_risk.json (live feed + fallback)
└── smoke.sh                # E2E CLI smoke tests (--offline option for CI)

docs/
├── guide/usage.md          # end-user CLI guide
├── architecture.md         # module layers + data flow + extension points
├── agents/                 # task-specific recipes for AI / human contributors
├── decisions/              # ADRs ("why we chose X over Y")
└── context-cards/          # one card per module — minimum context to edit it

tests/                      # pytest, ~74 cases
.github/workflows/
├── test.yml                # pytest 3.10/3.11/3.12 + offline smoke
└── refresh-tld-risk.yml    # monthly auto-PR for data/tld_risk.json
```

## Common commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Test
pytest -q                              # all tests
pytest -q tests/test_typosquat.py      # one module
bash scripts/smoke.sh --offline        # CLI E2E (no network)
bash scripts/smoke.sh                  # CLI E2E (hits Wayback)

# Run the CLI locally (works after `pip install -e .`)
dpf check example.com
dpf typosquat goolge.com
dpf llmo apple.com

# Refresh the bundled TLD risk table
python scripts/refresh_tld_risk.py --dry-run    # preview
python scripts/refresh_tld_risk.py              # write
```

## Design rules to follow when editing

These are not preferences; they are the load-bearing decisions behind the current code. Breaking them tends to break a test or a downstream check.

1. **Each check module owns one `*Report` dataclass.** Reports are pure data. Scoring lives in `score.py`, never in a check module.
2. **`score.py` is the only place that converts reports into deductions.** A check module surfacing a deduction value is a layer leak — fix the layering, not the symptom.
3. **All check module entry points are `check_<name>(domain: str, ...) -> SomeReport`.** Same shape across all 7 check modules. Match it when adding a new one.
4. **Network checks must be opt-in or fast.** Default `dpf check` invokes basic + history + typosquat + semantics + llmo (cheap). Anything slow (handles, trademark) is opt-in via `--check-*`.
5. **Parallel network calls go through `concurrent.futures.ThreadPoolExecutor`.** See `handles.py` and `trademark.py` for the pattern. Independent network checks SHOULD be concurrent; sequential I/O is a code smell here.
6. **Failures surface, not hide.** If a network call fails, the check returns a report with `status="lookup_failed"` and a `detail` string. The CLI shows it; the user decides. Silent fallthrough is forbidden.
7. **Bundled data lives in `data/` and is editable.** Brand lists, word lists, TLD risk JSON. PRs that *only* touch `data/` are first-class — no code change required.
8. **CLI option names follow a convention.** `--check-<name>` to enable an opt-in check. `--no-<name>` to disable a default-on check. Keep new flags consistent.

If a change conflicts with one of these rules, prefer reshaping the change.

## Conventions for AI coding agents specifically

- **Don't introduce a new dependency without a one-line justification in the commit message.** The whole package currently depends on `click + requests + rich + tldextract + Levenshtein`. Adding more must clear that bar.
- **Don't add comments that narrate the change ("Added in PR #N", "fixes the bug").** Comment only WHY (constraint, invariant, surprising behaviour). The PR description carries the rest.
- **Don't add a `--no-foo` flag and a `--check-foo` flag for the same check.** Pick one based on whether the check is fast enough to be default-on.
- **Don't refactor across multiple checks "while you're in there."** One check per change. The refactor instinct usually means the layering is being broken; see rule #2 above.
- **Every new check needs a smoke fixture in `scripts/smoke.sh`.** At least one GREEN/YELLOW/ORANGE/RED case that exercises the new path.

## Where the agent-friendliness is

- `docs/agents/` has recipes for the most common task shapes — read these *first* if you are adding code, before reading the existing modules.
- `docs/context-cards/` deliberately keeps each card under ~200 lines so a card can be loaded into a model's context without burning attention.
- ADRs in `docs/decisions/` answer "why" questions cheaply — load them when you suspect a constraint exists but is not documented in code.
- Every check module has the **same shape** so a coding agent can pattern-match: read one, you have read all.

## Where to push back

- This project is at v0.x. Heuristics and weights are *being calibrated*. If a deduction value or threshold looks wrong for a specific case, surface it — don't tune it silently to make a test pass.
- The `experimental` warning in the README is real, not boilerplate. Treat it that way.
