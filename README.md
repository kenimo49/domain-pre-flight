# domain-pre-flight

[![test](https://github.com/kenimo49/domain-pre-flight/actions/workflows/test.yml/badge.svg)](https://github.com/kenimo49/domain-pre-flight/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> ⚠️ **Status: experimental / under active validation.**
> Heuristics, score weights, and thresholds are still being calibrated against real-world domain decisions.
> Use it as one input — not the only one — when deciding whether to register a domain.

Pre-flight checks before registering a domain for a new site or app.

`domain-pre-flight` answers a single question: **"Is this domain safe to register for a new project, or should I keep looking?"**

It is **not** a domain investing / drop-catching tool. It is the last-mile checklist for engineers and founders who already have a domain in mind and want a quick read on whether it is clean, memorable, and free of obvious legacy abuse.

## What v0.1 does

| Check                      | What it tells you                                                                                   | Source            |
| -------------------------- | --------------------------------------------------------------------------------------------------- | ----------------- |
| Basic structural check     | length, hyphens, digits, IDN/punycode, syntactic validity (RFC 1035)                                | offline, no API   |
| TLD risk score             | per-TLD default risk based on Spamhaus / SURBL abuse statistics (.tk/.cf/.ml etc. heavily penalised) | static table      |
| Past content history       | Wayback Machine snapshot count, first/last archived date, archive span                              | archive.org (free, no auth) |
| Same-name handle check     | GitHub / npm / PyPI / X / Instagram availability for the SLD                                        | public APIs / HEAD requests |
| Typosquat / brand similarity | Levenshtein distance + homoglyph/bigram heuristics against ~120 widely-recognised brand stems     | bundled list, offline       |
| Trademark conflict (opt-in) | USPTO + EUIPO TMview search, J-PlatPat deeplink for manual review                                  | public registries, no auth  |
| Multi-language semantics    | Negative-meaning scan across EN / ES / PT / JA / KO / ZH (curated bundled lists)                    | bundled lists, offline      |
| LLMO fitness (experimental) | Pronunciation / memorability heuristic (cluster, vowel ratio, length, repeats) — 0–20 score          | offline heuristics          |
| Aggregate verdict          | 0–100 score, 4 bands (GREEN / YELLOW / ORANGE / RED), itemised deductions                           | derived           |

The CLI exits with `0` on GREEN/YELLOW, `1` on ORANGE, `2` on RED — convenient for CI gating in domain-procurement scripts.

## Install

```bash
pip install domain-pre-flight        # not yet on PyPI — install from source while v0.1 is in flight
# or, from a clone:
pip install -e ".[dev]"
```

## Usage

```bash
# Full check (basic + history + aggregate verdict)
domain-pre-flight check example.com

# Skip the network call to Wayback (offline only)
domain-pre-flight check example.com --no-history

# Include same-name handle availability across GitHub / npm / PyPI / X / Instagram
domain-pre-flight check example.com --check-handles

# JSON output for piping
domain-pre-flight check example.com --json

# History only
domain-pre-flight history example.com

# Handle availability only (subset selectable via --platforms)
domain-pre-flight handles example.com --platforms github,npm,pypi

# Typosquat / brand-similarity check only
domain-pre-flight typosquat goolge.com

# Trademark conflict (opt-in; queries USPTO + EUIPO, surfaces J-PlatPat deeplink)
domain-pre-flight check example.com --check-trademark
domain-pre-flight trademark example.com --jurisdictions us,eu

# Multi-language negative-meaning scan
domain-pre-flight semantics shineyo.com --languages ja

# LLMO fitness — pronunciation / memorability heuristic (experimental)
domain-pre-flight llmo apple.com

# Basic structural checks only
domain-pre-flight basic example.com

# Short alias
dpf check example.com
```

### Example output

```
example.com  →  GREEN  score=100/100  — Looks clean. Proceed.

Basic checks
┃ Field              ┃ Value
┃ SLD                ┃ example
┃ TLD                ┃ com
┃ length / SLD label ┃ 11 / 7
┃ hyphens / digits   ┃ 0 / 0
┃ IDN / punycode     ┃ no
┃ syntax valid       ┃ yes
┃ TLD risk score     ┃ 0
```

## Roadmap

The features below are planned but **not yet implemented**. Order is rough; PRs welcome.

### Near-term — eliminate the most common "should not have registered this" failure modes

1. ~~**Same-name social / package availability** — check whether the matching handle is free on GitHub, npm, PyPI, and major social networks.~~ **Shipped in v0.2** — `dpf handles` and `--check-handles`.
2. ~~**Typosquat / brand-similarity flag** — Levenshtein distance and bigram similarity against a curated brand list.~~ **Shipped in v0.3** — `dpf typosquat` (default ON in `dpf check`, disable with `--no-typosquat`).
3. ~~**Trademark conflict check** — query USPTO, EUIPO, and J-PlatPat for identical and confusingly similar marks.~~ **Shipped in v0.4** — `dpf trademark` and `--check-trademark` (opt-in). USPTO and EUIPO are queried live; J-PlatPat surfaces a deeplink for manual review. **This tool flags candidates, not legal opinions — consult counsel before acting on a flag.**

### Medium-term — quality-of-life and global readiness

4. ~~**Multi-language negative-meaning check** — scan the SLD against major languages (EN / ZH / ES / PT / KO / JA) for slurs, vulgarities, or unfortunate readings.~~ **Shipped in v0.5** — `dpf semantics` (default ON in `dpf check`, disable with `--no-semantics`). Word lists live at `data/negative_meanings/<lang>.txt` and accept community PRs with citations.
5. ~~**Per-TLD default risk score (deeper)** — extend the TLD table to use live Spamhaus / SURBL feed data instead of the static table.~~ **Refactored in v0.6** — TLD-risk table now lives at `data/tld_risk.json` and is loaded at runtime, with the embedded dict as a graceful fallback. `scripts/refresh_tld_risk.py` is the entry point; a monthly GitHub Actions workflow opens an auto-PR. Live feed integration (Interisle / DAAR) is currently a no-op stub — the script writes the curated baseline if no live source is available, so the bundle is always valid.
6. ~~**Pronunciation / memorability heuristics (LLMO fitness)** — score how easily the domain can be dictated, spelled-back over voice, and recognised by AI search assistants.~~ **Shipped in v0.7** — `dpf llmo` (default ON in `dpf check`, disable with `--no-llmo`). 0–20 fitness score across four axes (cluster / vowel / length / repeats); marked **experimental** in output because the heuristics are subjective and English-leaning.

### Opt-in — paid-API features (default OFF, not yet implemented)

7. **Detailed backlink evaluation** — referring-domain quality, anchor-text spam ratio, and historical link velocity from a paid provider (Ahrefs / Majestic / Moz). Will be exposed as an opt-in flag (planned name: `--enable-backlinks`) once the integration lands; provider and credentials will be configured via environment variables. Designed as a strict superset, not a replacement, for the free signals.

### Out of scope (for now)

- Domain valuation / sale-price history (drifts into domain-investing territory)
- WHOIS scraping for marketing intelligence
- Bulk domain monitoring (this is a per-decision pre-flight, not an asset-management tool)

## Design notes

- **Free signals first.** The default code path uses only public, no-auth APIs (Wayback Machine) and offline heuristics. Anything paid is opt-in.
- **Deterministic where possible.** The basic check and the score formula are pure functions; only the history check makes a network call.
- **Not a replacement for human judgement.** A green verdict is a "no obvious red flags," not a sign-off. Always inspect older Wayback snapshots manually before adopting a domain that has prior content.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Unit tests
pytest -q

# CLI smoke tests (offline mode skips the Wayback network call)
bash scripts/smoke.sh --offline
bash scripts/smoke.sh             # full run, hits Wayback Machine
```

CI runs `pytest` against Python 3.10 / 3.11 / 3.12 plus the offline smoke suite on every push and PR.

## License

MIT — see [LICENSE](LICENSE).

## Background

This project is a tools-side companion to the (Japanese-language) book
**「2人ではじめる中古ドメイン・ビジネス: 目利き×運用の協業設計」** by Ken Imoto,
which covers expired-domain-abuse policy boundaries, LLMO-era authority
evaluation, revenue-share contracts, and exit-route economics for
domain-and-content businesses. `domain-pre-flight` distils the
"will I regret registering this name?" pre-flight subset of that material
into a runnable check.
