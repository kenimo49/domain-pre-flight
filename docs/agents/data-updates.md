# Recipe: Data-only updates

When the change you want to make is *purely data* — adding a brand stem, a negative-meaning term, or a TLD risk score — you do not need to touch any Python file. This recipe shows the right place to land each.

PRs that only touch `data/` are welcomed. They merge faster and the diff is reviewable by anyone, not just Python readers.

## Updating the brand list (`data/known_brands.txt`)

Used by the typosquat check.

Format: one lowercase brand stem per line. Comments start with `#`. Blank lines and section headers are allowed.

```text
# Tech giants
google
apple
microsoft

# Streaming
netflix
spotify
```

Rules:

- Use the **stem typical users would type as a domain**, not the legal name. `cocacola`, not `coca-cola company`.
- Lowercase, no whitespace, no punctuation.
- Avoid stems shorter than 4 characters — they cannot match anyway (typosquat exempts short SLDs from similarity matching) and they would just clutter the iteration.
- One brand per line. No grouping, no synonyms; if both `meta` and `facebook` are typosquat-relevant, list them on separate lines.

How to verify your change:

```bash
.venv/bin/dpf typosquat <something-resembling-the-new-brand>.com
pytest -q tests/test_typosquat.py
```

The list will eventually be replaced by an auto-refreshed Tranco-derived list (issue is on the roadmap). Until then, hand-curated additions are the right path.

## Adding a negative-meaning term (`data/negative_meanings/<lang>.txt`)

Used by the semantics check.

Format: `term[<TAB>severity]`. Severity defaults to `mild`; specify `severe` explicitly when needed.

```text
# Spanish (LatAm-neutral)
puta	severe
mierda	severe
muerte	mild
```

Rules:

- **Cite your source.** PRs adding terms must include a citation (LDNOOBW, Wiktionary, published moderation list). The repo deliberately curates rather than crowd-sources to avoid the GPT-generated-slur trap.
- Pick severity conservatively. `severe` triggers issue-level warnings; reserve it for terms whose presence in an SLD is unambiguous. Borderline goes `mild`.
- Watch for substring false positives. `sex` (3 chars) is exempt from substring matching, but `sex` (severe, exact-only) is fine to keep. A 4+ char term will substring-match — only add it if that match is the desired behaviour.
- Romanised forms only. The check operates on the SLD, which is ASCII; do not include native-script entries (they will never match).

Languages supported today:

- `en` (English)
- `es` (Spanish — LatAm-neutral first)
- `pt` (Portuguese — BR-priority)
- `ja` (Japanese romaji)
- `ko` (Korean romanised)
- `zh` (Mandarin pinyin)

To add a new language, also extend `SUPPORTED_LANGUAGES` in `src/domain_pre_flight/checks/semantics.py`.

How to verify:

```bash
.venv/bin/dpf semantics <test-domain>.com --languages <lang>
pytest -q tests/test_semantics.py
```

## Updating the TLD risk table (`data/tld_risk.json`)

Used by the basic check.

Two paths:

### Manual edit

Edit the file directly. Schema:

```json
{
  "version": 1,
  "generated_at": "2026-MM-DDTHH:MM:SSZ",
  "sources": ["..."],
  "scale": "0 = trusted; 70 = heavily abused. Unknown TLDs default to 25.",
  "risk": {
    "com": 0,
    "tk": 70
  }
}
```

Rules:

- Lowercase TLD keys.
- Integer scores 0–70 inclusive.
- Bump `generated_at` to today's UTC date when you edit.
- Add the source to `sources` if you used a new feed.

### Refresh script

`scripts/refresh_tld_risk.py` writes the same file. Useful when you want the timestamp updated even without changing values:

```bash
python scripts/refresh_tld_risk.py --dry-run    # preview
python scripts/refresh_tld_risk.py              # write
```

The script falls back to the curated baseline when no live feed is available (current state). When a redistributable live feed appears, plug it into `_try_fetch_*` functions inside the script.

How to verify:

```bash
.venv/bin/dpf basic something.<your-edited-tld>
pytest -q tests/test_tld_risk_bundle.py
```

## When data-only is *not* enough

- Adding a whole new language list → also touches `SUPPORTED_LANGUAGES` in `checks/semantics.py`. See [`extending-checks.md`](extending-checks.md).
- Changing the brand-list **format** (tabs, severity, etc.) → that's a code change.
- Changing scoring of a TLD across the board → that's a `score.py` change, not a data change. See [`tuning-scores.md`](tuning-scores.md).
