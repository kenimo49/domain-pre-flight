# Architecture

This document is the second-deepest layer after [`CLAUDE.md`](../CLAUDE.md). Read it before editing across module boundaries.

## Layer diagram

```
                     ┌──────────────────────────────────┐
                     │             cli.py               │  ← orchestration + rendering
                     │  click commands, JSON, exit codes│
                     └──────────────┬───────────────────┘
                                    │ calls
                ┌──────────────┬────┴───┬─────────────┬────────────────┐
                ▼              ▼        ▼             ▼                ▼
       ┌────────────┐  ┌────────────┐  ...    ┌──────────────┐  ┌──────────────┐
       │ check_basic│  │check_history│       │check_typosquat│  │  check_llmo  │
       │ (basic.py) │  │(history.py) │       │(typosquat.py) │  │  (llmo.py)   │
       └─────┬──────┘  └─────┬──────┘         └──────┬───────┘  └──────┬───────┘
             │ returns       │                       │                 │
             ▼               ▼                       ▼                 ▼
       BasicReport     HistoryReport            TyposquatReport     LlmoReport
             │               │                       │                 │
             └─────────┬─────┴───────────────────────┴────────────────┘
                       ▼
                ┌──────────────┐
                │  aggregate   │  (score.py)
                │ Reports → Verdict (score, band, deductions)
                └──────────────┘
```

Three rules govern this layout:

1. **Reports flow up, not sideways.** A check module never imports another check module's *report logic* (text, severity rules). Import only what is needed; cross-check coordination happens in `cli.py` and `score.py`.
2. **`score.py` is the single converter.** Reports → deductions → Verdict. Every check module's contribution to the score is gathered here, in one place, so weights are auditable in one read.
3. **`cli.py` is the only thing that knows about Click, `rich`, and JSON output.** Check modules and `score.py` are pure-Python; you can call them from a notebook, library, or test without dragging the CLI surface in.

## Module-by-module responsibility

### `cli.py`

- Defines all Click commands (`check`, `basic`, `history`, `handles`, `typosquat`, `trademark`, `semantics`, `llmo`).
- Maps the verdict band to an exit code via `EXIT_CODES`.
- Owns rendering helpers (`_basic_table`, `_typosquat_table`, …) and the JSON payload builder (`_payload`).
- Should not contain any check logic. If a piece of behaviour can be tested without a `CliRunner`, it does not belong here.

### `checks/basic.py`

- Offline structural validation: hostname syntax (RFC 1035), length, hyphens, digits, IDN, SLD/TLD split.
- Loads `data/tld_risk.json` at import time; falls back to an embedded dict if the JSON is missing or corrupt.
- Exports `parse_domain()` (used by every other check), `check_basic()` (returns a `BasicReport`), and `tld_risk_for(tld)` (used by `score.py`).
- **Owns no scoring math.** It surfaces facts (e.g. *"hyphens=3"*) and human-readable hints (*"3 hyphens — looks spammy"*), but the points-per-hyphen weight lives in `score.py`.

### `checks/history.py`

- Three small CDX queries: first snapshot (`limit=1`), last snapshot (`limit=-1`), bounded count (`limit=2000`).
- Returns `HistoryReport` with `has_archive`, `snapshot_count` (saturated at 2000), `first_seen`, `last_seen`, `age_days`.
- Free, no auth, gentle on archive.org. Failures surface as `issues=[…]` rather than exceptions.

### `checks/handles.py`

- Five platform checkers, each returning `HandleResult(platform, status, detail)`.
- `status` ∈ {`taken`, `available`, `unknown`}. Bot-walled platforms (X, Instagram) intentionally fall through to `unknown` rather than misreport.
- `check_handles()` fans out via `ThreadPoolExecutor(max_workers=5)`.
- Public registry `PLATFORM_CHECKS: dict[str, callable]` — extending the platform set is one line.

### `checks/typosquat.py`

- Levenshtein + homoglyph + bigram-set heuristics against a curated brand list (`data/known_brands.txt`).
- Emits `BrandMatch(brand, distance, kind)` records with `kind ∈ {exact, near, possible, homoglyph, bigram}`.
- SLDs shorter than 4 characters are exempt from similarity matching to avoid trigger-happy "distance 2 to 'lg'" noise.
- Pure Python, no network, deterministic.

### `checks/trademark.py`

- Three jurisdictions: USPTO (live), EUIPO (live), J-PlatPat (deeplink only — no public API).
- Per-jurisdiction status: `ok` / `lookup_failed` / `not_supported`.
- Concurrent fan-out via `ThreadPoolExecutor`. Slow enough that it is **opt-in** by default.
- Surfaces *candidates*, not legal opinions. The disclaimer in the report text is intentional.

### `checks/semantics.py`

- Six bundled per-language word lists at `data/negative_meanings/<lang>.txt`. Format: `term[\tseverity]`.
- Match modes: `exact` (SLD == term) and `substring` (SLD contains term). Substring matching only applies to terms ≥4 chars.
- Severity tiers: `severe` → issue, `mild` → note.

### `checks/llmo.py`

- Four offline heuristic axes (cluster, vowel, length, repeats), each 0–5; total fitness 0–20.
- Bands: excellent (≥16) / good (≥11) / ok (≥6) / poor (<6). Only `poor` and `ok` deduct points.
- Marked **experimental** in CLI output. English-leaning by design.

### `checks/score.py`

- Defines the `Band` enum, the score thresholds, the `EXIT_CODES` map.
- One `_<name>_deductions(report)` function per check module. **All weights are visible in this single file.**
- `aggregate(basic, history=None, typosquat=None, trademark=None, semantics=None, llmo=None)` is the single integration point.

## Data flow for `dpf check`

```
domain → check_basic(domain) ─────────────────────┐
       → check_history(domain) ───────────────────┤
       → check_typosquat(domain) ─────────────────┤
       → check_semantics(domain) ─────────────────┼──► aggregate(...) → Verdict
       → check_llmo(domain) ──────────────────────┤                       │
       → [opt-in] check_handles(domain) ──────────┤                       │
       → [opt-in] check_trademark(domain) ────────┘                       │
                                                                          ▼
                                                              cli._render_verdict
                                                              cli._payload (JSON)
                                                              EXIT_CODES[band]
```

The `dpf` subcommands `basic / history / handles / typosquat / trademark / semantics / llmo` short-circuit this flow: they call exactly one check function and render only that report. Useful for iterating on one axis or for scripting.

## Extension points

| You want to…                                  | Touch                                         |
| --------------------------------------------- | --------------------------------------------- |
| Add a new platform to the handle check        | `checks/handles.py::PLATFORM_CHECKS` + a new `check_<platform>` function + smoke + tests |
| Add a new check axis entirely                 | New `checks/<name>.py` + `score.py::_<name>_deductions` + new flag in `cli.py::check` + smoke + tests + ADR explaining the design |
| Tune a deduction weight                       | `score.py::_<name>_deductions` only          |
| Add brand stems                               | `data/known_brands.txt`                      |
| Add words to a language list                  | `data/negative_meanings/<lang>.txt`          |
| Refresh the TLD risk table                    | `python scripts/refresh_tld_risk.py`         |
| Add a new language to the semantics scan      | `data/negative_meanings/<lang>.txt` + `SUPPORTED_LANGUAGES` in `checks/semantics.py` |
| Tighten the typosquat thresholds              | `checks/typosquat.py::EXACT_MATCH / NEAR_DISTANCE / POSSIBLE_DISTANCE` |
| Change Wayback query budget                   | `checks/history.py::COUNT_LIMIT`             |

Most of these are 5-line changes because the architecture deliberately puts knobs at the leaf level.

## Dependency graph (runtime)

```
click          — CLI
requests       — HTTP for Wayback / handles / trademark
rich           — terminal rendering, optional from a library standpoint
tldextract     — PSL-aware SLD/TLD split
Levenshtein    — fast edit distance for typosquat
```

That is the entire runtime dependency surface. New dependencies need to clear a per-PR justification bar (see `CLAUDE.md`).

## Why the architecture looks like this

See `docs/decisions/` for the recorded ADRs:

- **0001** — `tldextract` over hand-rolled or `publicsuffixlist`
- **0002** — `Band` as `(str, Enum)` rather than `StrEnum` (3.10 compatibility)
- **0003** — TLD risk in JSON bundle with embedded fallback
- **0004** — Wayback `limit=2000` instead of `limit=5000`
- **0005** — Bot-walled platforms return `unknown`, not `available`
- **0006** — Trademark check defaults to OFF
- **0007** — Score weights centralised in `score.py`

If you are about to undo one of those, read the ADR first.
