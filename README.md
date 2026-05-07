# domain-pre-flight

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

# JSON output for piping
domain-pre-flight check example.com --json

# History only
domain-pre-flight history example.com

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

1. **Trademark conflict check** — query USPTO TSDR API, J-PlatPat, and EUIPO for identical and confusingly similar marks. The single biggest reason new sites get yanked after launch (UDRP / trademark complaint), so this is a near-must-have.
2. **Same-name social / package availability** — check whether the matching handle is free on GitHub, npm, PyPI, and major social networks (HEAD requests / public APIs). Naming consistency materially affects whether the domain is worth taking.
3. **Typosquat / brand-similarity flag** — Levenshtein distance and bigram similarity against a Tranco top-N list. Avoids unintentionally registering a name that resembles a major brand and risks a UDRP filing.

### Medium-term — quality-of-life and global readiness

4. **Multi-language negative-meaning check** — scan the SLD against major languages (EN / ZH / ES / PT / KO and others) for slurs, vulgarities, or unfortunate readings. Important once a project has any chance of going global.
5. **Per-TLD default risk score (deeper)** — extend the TLD table to use live Spamhaus / SURBL feed data instead of the static table currently shipped.
6. **Pronunciation / memorability heuristics (LLMO fitness)** — score how easily the domain can be dictated, spelled-back over voice, and recognised by AI search assistants. Non-trivial signal for any project that expects to be cited by LLM-driven discovery surfaces.

### Opt-in — paid-API features (default OFF)

7. **Detailed backlink evaluation** — opt-in via `--enable-backlinks`. Reads referring-domain quality, anchor-text spam ratio, and historical link velocity from a paid backlink provider (Ahrefs / Majestic / Moz). Default OFF so the tool stays usable without keys; provider and credentials are configured via environment variables when enabled. Designed as a strict superset, not a replacement, for the free signals.

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

pytest -q
```

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
