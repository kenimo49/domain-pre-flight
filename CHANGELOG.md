# Changelog

All notable changes to **domain-pre-flight** are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely; versions follow [SemVer](https://semver.org/) with the convention that **0.x is experimental** — breaking changes can land on a minor bump.

## [0.10.0] — 2026-07-07

### Added

- **`--suggest` flag** for `dpf check` — after the pre-flight verdict, generates related emerging-term `.com` domain candidates via Anthropic claude-haiku, checks each for RDAP availability (tri-state: free / taken / inconclusive), and surfaces a 30-day Hacker News mention count as a trend signal. Requires `pip install domain-pre-flight[suggest]` and `ANTHROPIC_API_KEY`. Gracefully degrades when either is absent.
- **`--suggest-count N`** — controls how many candidates to generate (default 5, minimum 1).
- **`suggest` optional extra** — `pip install domain-pre-flight[suggest]` pulls `anthropic>=0.25`.
- **16 → 25 unit tests** for the suggest module: RDAP tri-state, HN signal thresholds, `_generate_terms` parse/sanitize, CLI integration (JSON payload, missing-key fallback, count validation).

### Changed

- `anthropic>=0.25` added to `dev` extra so the full test suite runs without installing `[suggest]` separately.
- `--suggest-count` validated with `click.IntRange(min=1)`; `0` and negative values are rejected at the CLI layer.

## [0.9.0] — 2026-07-07

### Added

- **MCP server** (`domain-pre-flight[mcp]`) — new optional extra and `domain-pre-flight-mcp` entry point. Ships an MCP (Model Context Protocol) server built on FastMCP so AI assistants (Claude Code / Cursor / Claude Desktop) can call the checks as tools. Exposes 4 use-case-oriented tools rather than mapping every CLI flag: `check_domain`, `check_handles`, `check_trademark`, `list_typo_permutations`.
- **Subprocess-variant reference implementation** — `examples/subprocess-variant/` ships a deliberately naive subprocess-based MCP server plus a benchmark script (`bench.py`) as the "before" half of a security / latency comparison. Not for production.
- **PyPI publishing workflow** — `.github/workflows/publish.yml` publishes to PyPI via Trusted Publisher OIDC on every `v*` tag push; no long-lived API tokens.

### Changed

- `pyproject.toml` gains `[project.optional-dependencies].mcp = ["mcp>=1.2"]` and `[project.scripts].domain-pre-flight-mcp = "..."`. Core CLI users are unaffected — the `mcp` dependency only installs when `[mcp]` is requested.
- `release.yml` no longer holds a `PYPI_API_TOKEN` fallback path; PyPI publishing is centralised in `publish.yml`.

## [0.8.0] — 2026-05-08

### Added

- **IDN homograph detection** — new `dpf homograph` subcommand and `--no-homograph` flag. UTS #39 confusable matching against the brand list. `gооgle.com` (Cyrillic о) is flagged as a brand collision.
- **RDAP lifecycle check** — new `dpf rdap` subcommand and `--check-rdap` flag. Surfaces creation date, expiration date, registrar, and registry status (clientHold / redemptionPeriod / etc.) via the rdap.org public gateway.
- **DNS hygiene check** — new `dpf dns` subcommand and `--check-dns` flag. Probes MX / SPF / DMARC / DKIM presence; flags MX-without-SPF / MX-without-DMARC as deductions.
- **dnstwist-style permutations** — new `dpf permutations` subcommand. Generates 8 kinds of typo / spoof variants (omission, transposition, doubling, homoglyph, keyboard_adjacent, substitution, addition, hyphenation).
- **GitLab handle availability** — added to `dpf handles` defaults.
- **5 new languages** in semantics: Hindi (`hi`), Arabic (`ar`), Vietnamese (`vi`), Thai (`th`), Indonesian (`id`). Romanised forms only.
- **LLMO locale profile** — `--llmo-locale en|neutral`. Neutral mode relaxes the cluster ceiling so transliterated names (roomaji, pinyin) aren't unfairly penalised.
- **Tranco-driven brand list refresh** — `scripts/refresh_known_brands.py` + monthly `refresh-known-brands` workflow.
- **CI quality gates** — ruff lint job, mypy type job, pytest with `--cov-fail-under=70` (cli.py omitted from coverage).
- **Project hygiene files** — `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md`, `release.yml` workflow.

### Changed

- **Trademark module** — every jurisdiction now resolves to `not_supported` + deeplink (no live API queries). See ADR 0009. Doc drift in `CLAUDE.md`, `docs/architecture.md`, and `docs/guide/usage.md` swept to match.
- **Skill** — `argument-hint` accepts multiple domains; multi-domain output spec added (comparison table → ranking → top-3 trademark verify checklist → next step).

### Fixed

- `_de_confuse` previously rewrote ASCII characters into other confusables; now only non-Latin characters are de-confused (preserves Latin SLDs unchanged).

### Internal

- `basic.normalise(domain) → (domain, sld, tld)` shared helper, replaces 5 duplicated normalisation passes across check modules.
- Ten check modules now share consistent shapes (`check_<name>(domain) → <Name>Report` returning `issues` + `notes`).

## [0.7.2] — 2026-05-08

### Changed

- Skill multi-domain mode + top-3 trademark verify checklist (9 links instead of 24).

## [0.7.0] — 2026-05-08

### Added

- ROADMAP issues #1–#6 all shipped: same-name handle availability, typosquat / brand similarity, trademark deeplinks, multi-language semantics, refreshable TLD risk JSON, LLMO fitness heuristic.

## [0.1.0] — 2026-05-08

### Added

- Initial public release. `dpf check / basic / history`, scoring engine, GREEN / YELLOW / ORANGE / RED bands.
