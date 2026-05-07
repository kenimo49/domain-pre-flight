# Changelog

All notable changes to **domain-pre-flight** are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) loosely; versions follow [SemVer](https://semver.org/) with the convention that **0.x is experimental** — breaking changes can land on a minor bump.

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
