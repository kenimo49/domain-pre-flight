# Usage Guide

This guide walks through every CLI subcommand of `domain-pre-flight` and shows the situations each one is designed for.

> Throughout this guide the long form `domain-pre-flight` and the short alias `dpf` are interchangeable.

## Table of contents

- [Install](#install)
- [Two ways to use it](#two-ways-to-use-it)
- [Subcommand reference](#subcommand-reference)
  - [`dpf check`](#dpf-check) — full verdict
  - [`dpf basic`](#dpf-basic) — offline structural checks
  - [`dpf history`](#dpf-history) — Wayback Machine history
  - [`dpf handles`](#dpf-handles) — same-name availability across platforms
  - [`dpf typosquat`](#dpf-typosquat) — brand-similarity flag
  - [`dpf trademark`](#dpf-trademark) — USPTO / EUIPO / J-PlatPat
  - [`dpf semantics`](#dpf-semantics) — multi-language negative-meaning scan
  - [`dpf llmo`](#dpf-llmo) — pronunciation / memorability heuristic
- [Workflows by scenario](#workflows-by-scenario)
- [Score, bands, and exit codes](#score-bands-and-exit-codes)
- [JSON output](#json-output)
- [Extending the tool](#extending-the-tool)

## Install

```bash
git clone https://github.com/kenimo49/domain-pre-flight
cd domain-pre-flight
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify the install:

```bash
dpf --version
```

## Two ways to use it

### As an interactive triage tool

Run `dpf check <domain>` while you are deciding whether to register a name. The output is a colourised verdict, an itemised score breakdown, and (for borderline cases) per-axis details that tell you *why* a name dropped a band.

### As a CI gate / scripted pre-flight

`dpf check` exits with a code that maps to the verdict band:

| Band     | Score   | Exit code |
| -------- | ------- | --------- |
| GREEN    | 90–100  | 0         |
| YELLOW   | 70–89   | 0         |
| ORANGE   | 40–69   | 1         |
| RED      | 0–39    | 2         |

This makes it usable inside a procurement script:

```bash
if dpf check --json "$candidate" > report.json; then
  echo "ok to register"
else
  echo "skip: $(jq -r '.verdict.summary' report.json)"
fi
```

## Subcommand reference

### `dpf check`

Run every enabled check on the domain and emit a single verdict.

```text
dpf check DOMAIN [OPTIONS]
```

**Default behaviour** (offline + cheap online only):

- basic structural checks
- Wayback Machine history
- typosquat / brand-similarity check
- multi-language negative-meaning scan
- LLMO fitness heuristic

Slow or opt-in checks **must be enabled explicitly**:

| Flag                       | Effect                                                              |
| -------------------------- | ------------------------------------------------------------------- |
| `--check-handles`          | Add GitHub / npm / PyPI / X / Instagram availability                |
| `--check-trademark`        | Query USPTO + EUIPO + J-PlatPat deeplink                            |
| `--trademark-jurisdictions`| Subset for `--check-trademark` (default `us,eu,jp`)                 |
| `--no-history`             | Skip the Wayback Machine call (offline-only)                        |
| `--no-typosquat`           | Skip the typosquat check                                            |
| `--no-semantics`           | Skip the multi-language negative-meaning scan                       |
| `--no-llmo`                | Skip the pronunciation / memorability heuristic                     |
| `--languages`              | Comma-separated language subset for the semantics scan              |
| `--json`                   | Emit JSON to stdout instead of a rich table                         |

Example — full check including handles, trademark, all languages:

```bash
dpf check mybrand.com --check-handles --check-trademark
```

### `dpf basic`

Just the offline structural checks (length, hyphens, digits, IDN, TLD risk hint, syntactic validity). No network.

```bash
dpf basic mybrand.com
dpf basic mybrand.com --json
```

Use this when:

- you want a sub-second sanity check on a candidate
- you are running in an air-gapped / sandboxed environment
- you want to script-check 10,000 candidates without hitting any external service

### `dpf history`

Wayback Machine snapshot count, first/last archived timestamps, archive span.

```bash
dpf history nicebrand.com
```

Use this when:

- a domain looks "too good" — you suspect it has prior content
- you are evaluating an aftermarket / drop-catch acquisition
- you want to know whether to manually inspect older Wayback snapshots before adopting the topic

The check uses three light queries (first / last / bounded count, capped at 2,000 rows) to stay friendly to archive.org.

### `dpf handles`

Same-name availability across developer platforms and social networks.

```bash
dpf handles mybrand.com
dpf handles mybrand.com --platforms github,npm,pypi
```

Status meanings:

- **`taken`** — a profile or package with this name exists
- **`available`** — confirmed not present
- **`unknown`** — could not determine (rate limit, bot wall, transport error)

Twitter and Instagram frequently return `unknown` because of bot protection. The tool says so explicitly rather than risk a misleading "available."

Use this when:

- naming consistency matters for the project (most product launches)
- you want to know whether the matching npm / PyPI package name is free before committing to a domain

GitHub anonymous rate limit is 60 requests/hour. For the per-decision usage this tool is built for, that is comfortably enough.

### `dpf typosquat`

Brand-similarity check using Levenshtein distance plus homoglyph and bigram heuristics, against a curated bundled brand list (`data/known_brands.txt`, ~120 widely-recognised stems).

```bash
dpf typosquat goolge.com
dpf typosquat micr0soft.com
```

Match kinds:

| Kind        | What it catches                                       | Behaviour                |
| ----------- | ----------------------------------------------------- | ------------------------ |
| `exact`     | SLD identical to a known brand                        | Issue, heavy deduction   |
| `near`      | Levenshtein distance 1 or 2 to a brand                | Issue, medium deduction  |
| `homoglyph` | De-substituted form (`g00gle` → `google`) is a match  | Issue, medium deduction  |
| `bigram`    | Same bigram set as a brand, different ordering        | Issue, light deduction   |
| `possible`  | Levenshtein distance 3                                | Note only, no deduction  |

Short SLDs (under 4 chars) are exempt from similarity matching to avoid trigger-happy false positives like "distance 2 to 'lg'".

Use this when:

- you want to avoid registering a name that resembles a major brand and would invite a UDRP filing

### `dpf trademark`

Query trademark registries for marks similar to the SLD.

```bash
dpf trademark mybrand.com
dpf trademark mybrand.com --jurisdictions us,eu
```

Per jurisdiction:

- **USPTO** (US) — live query against `tmsearch.uspto.gov`
- **EUIPO** (EU) — live query against `tmdn.org` TMview
- **J-PlatPat** (JP) — no public API; the report surfaces a pre-filled deeplink for manual verification

Status meanings:

- **`ok`** — query succeeded; results may be empty
- **`lookup_failed`** — transport / API error; retry or use the deeplink
- **`not_supported`** — no public, redistributable query path; deeplink only

> **This tool flags candidates, not legal opinions.** "Confusingly similar" is a legal standard, not a string-distance threshold. Consult counsel before acting on a flag.

Use this when:

- you are about to commit a brand name to a real launch
- you have already passed the cheaper checks (`typosquat`, `semantics`) and want to clear the legal-risk axis

### `dpf semantics`

Multi-language negative-meaning scan for the SLD across English, Spanish, Portuguese, Japanese, Korean, and Chinese.

```bash
dpf semantics shineyo.com --languages ja
dpf semantics getputaway.com --languages pt
dpf semantics anything.com   # all six languages by default
```

Word lists live at `src/domain_pre_flight/data/negative_meanings/<lang>.txt` and are curated, not crowd-sourced. PRs adding terms must include a citation.

Severity tiers:

- **`severe`** — slurs and unambiguously bad terms; an exact match becomes an issue
- **`mild`** — generally undesirable terms (vulgar but not slur-tier); only a note

Substring matching only kicks in for terms 4+ characters long, so a clean name like `essex.com` does not get flagged for containing `sex`.

Use this when:

- a project has any chance of going global (the dominant case for new SaaS names)
- the domain looks fine in English but you have not eyeballed it in other major-market languages

### `dpf llmo`

Pronunciation / memorability heuristic. Marked **experimental** — heuristics are subjective and English-leaning, but they catch a class of "looks fine on paper, terrible to dictate" names.

```bash
dpf llmo apple.com
dpf llmo strngths.com
```

Output is a 0–20 fitness score, summed across four axes (each 0–5):

| Axis      | Penalises                                                          |
| --------- | ------------------------------------------------------------------ |
| `cluster` | Long consecutive consonant runs (`strngths` has cluster of 8)      |
| `vowel`   | Vowel ratios outside the 0.30–0.55 sweet spot                      |
| `length`  | SLDs outside the 4–9 char "memorable" window                       |
| `repeats` | Long runs of the same character (`zzzzbrand`)                      |

Bands:

- **excellent** ≥ 16
- **good** ≥ 11
- **ok** ≥ 6
- **poor** < 6

Only `poor` and `ok` produce a score deduction (10 and 3 respectively).

Use this when:

- the name will be spoken on podcasts, voice search, or AI assistants
- you are choosing between two structurally-similar candidates and want a tiebreaker

## Workflows by scenario

### "I want to register `myapp.io` for a side project — quick check"

```bash
dpf check myapp.io
```

Done. Sub-second turnaround for the offline checks, ~1 second for Wayback.

### "I am about to commit a brand name for a real product launch"

```bash
dpf check mybrand.com --check-handles --check-trademark
```

This adds the slow checks (handle availability + trademark queries) and gives you the most complete pre-flight the tool can produce. Plan for ~10 seconds.

### "I am evaluating an expired domain in an aftermarket"

```bash
dpf history candidate.com           # how heavily was this used before?
dpf check candidate.com              # any structural / brand / semantic flags?
```

The `history` subcommand is the headline check here. Manually inspect early/late Wayback snapshots before adopting the topic.

### "I have a list of 100 candidates and want to filter the obviously-bad ones"

```bash
while IFS= read -r d; do
  if dpf check --no-history --json "$d" > /tmp/r.json; then
    band=$(jq -r '.verdict.band' /tmp/r.json)
    score=$(jq -r '.verdict.score' /tmp/r.json)
    echo "$d $band $score"
  else
    echo "$d FAIL"
  fi
done < candidates.txt | sort -k2,2
```

`--no-history` keeps it offline, so 100 candidates take seconds, not minutes.

### "Pre-flight inside a CI domain-procurement pipeline"

```yaml
- name: Pre-flight the candidate domain
  run: |
    dpf check "${{ inputs.domain }}" --check-handles --check-trademark
  # Exit codes: 0 GREEN/YELLOW, 1 ORANGE, 2 RED. Job fails on ORANGE+.
```

## Score, bands, and exit codes

The aggregate verdict starts at 100 and is reduced by each contributing check's deductions, capped at 100 total deduction. The 4-band mapping is:

| Score    | Band   | Exit code |
| -------- | ------ | --------- |
| 90–100   | GREEN  | 0         |
| 70–89    | YELLOW | 0         |
| 40–69    | ORANGE | 1         |
| 0–39     | RED    | 2         |

Each deduction shows up in the rendered table or in `verdict.deductions[]` of the JSON output, so you can audit *why* a verdict landed where it did.

## JSON output

Every subcommand supports `--json`. The `dpf check` payload looks like:

```json
{
  "domain": "example.com",
  "verdict": { "score": 100, "band": "GREEN", "summary": "...", "deductions": [] },
  "basic":     { ... },
  "history":   { ... },
  "handles":   null,
  "typosquat": { ... },
  "trademark": null,
  "semantics": { ... },
  "llmo":      { ... }
}
```

`null` values mean the corresponding check was disabled or skipped for that invocation.

## Extending the tool

- **Brand list**: edit `src/domain_pre_flight/data/known_brands.txt`. One lowercase stem per line; comments start with `#`.
- **Negative-meaning lists**: edit `src/domain_pre_flight/data/negative_meanings/<lang>.txt`. Format: `term[\tseverity]`. PRs must include a citation per term.
- **TLD risk table**: regenerate `src/domain_pre_flight/data/tld_risk.json` by running `python scripts/refresh_tld_risk.py`. The script tries optional live feeds and falls back to the curated baseline.
- **A new check**: add a new module under `src/domain_pre_flight/checks/`, expose a `check_<name>(domain) -> SomeReport` function, wire it into `cli.py` and (if it should affect the score) `score.py::aggregate`. Existing checks are good templates — `handles.py` shows the parallel-network pattern, `typosquat.py` shows the offline-data pattern.
