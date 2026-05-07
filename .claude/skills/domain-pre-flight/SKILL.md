---
name: domain-pre-flight
description: Pre-flight checks before registering a domain for a new site or app. Runs structural / history / typosquat / multi-language / LLMO checks against one or more candidates, optionally adds same-name handle availability and trademark deeplinks, and returns per-domain verdict bands plus (when given multiple candidates) a comparison table and a top-3 trademark verify checklist. Use when the user is choosing a domain, evaluating a brainstorm shortlist, or wants a sanity check before pulling the trigger on a registrar.
argument-hint: <domain> [<domain> ...] [--full] [--handles] [--trademark]
allowed-tools: Bash, Read
---

# domain-pre-flight skill

Run pre-flight checks before the user registers a new domain. The CLI lives at https://github.com/kenimo49/domain-pre-flight; this skill is the conversational wrapper around it.

## When to invoke

Use this skill when the user:

- explicitly asks "is this domain safe to register" / "can I take X.com" / "ドメイン取って大丈夫？"
- gives a list of candidate domains and asks which one to pick
- mentions registering a name and you want to add a sanity check before they spend money
- references the companion book `domain-hunter-engineer-collab` or "domain hunter" workflow

Do NOT invoke when:

- the user is asking about a domain they already own (use the trademark / typosquat subcommands manually if needed, but the full pre-flight is for unregistered candidates)
- the question is about domain investing / aftermarket / drop-catching (out of scope for this tool)

## How it works

1. **Resolve the CLI.** Try in this order and use the first that exists:
   ```bash
   DPF=$(command -v dpf 2>/dev/null \
     || command -v domain-pre-flight 2>/dev/null \
     || ([ -x "$HOME/repos/domain-pre-flight/.venv/bin/dpf" ] && echo "$HOME/repos/domain-pre-flight/.venv/bin/dpf"))
   ```
   If `$DPF` is empty, see the install section below.
2. **Detect single vs multi.** If the user gave one domain, follow the [single-domain](#single-domain) flow. If two or more, follow the [multi-domain](#multi-domain) flow.
3. **Always pass `--json`** to the CLI and parse with `python3 -c 'import json, sys; ...'`. Never read coloured terminal output.

## Install (only if `$DPF` did not resolve)

```bash
# Recommended — pipx isolates the CLI in its own venv but exposes `dpf` on PATH
pipx install git+https://github.com/kenimo49/domain-pre-flight.git

# Or, from a local clone in editable mode
pip install -e /home/iris/repos/domain-pre-flight
```

## Single-domain

```bash
"$DPF" check "$domain" --json                                # quick (default)
"$DPF" check "$domain" --check-handles --check-trademark --json   # full pre-flight
```

Runs basic + history + typosquat + semantics + llmo (`--json` always). The `--check-handles` and `--check-trademark` flags are opt-in for slower / network-heavy / manual-verify paths.

Summarise in 3–6 lines:

```
**<domain>**: <band> — score <N>/100

What flagged:
- <deduction reason 1>: -<points>
- <deduction reason 2>: -<points>

Recommendation: <one sentence — register, walk away, or run a deeper check>
```

Keep the report under ~6 lines unless the user asks for the full breakdown. The `verdict.deductions` list in the JSON is the source of truth — quote it directly rather than paraphrasing (the wording is calibrated).

If a check returned `lookup_failed` or `unknown` (e.g. handles bot wall), say so explicitly. Do not pretend you got a clean answer.

## Multi-domain

Run the candidates in parallel via background bash jobs, write each to a temp JSON, then aggregate. Pattern:

```bash
mkdir -p /tmp/dpf-batch
DOMAINS=("$@")  # the user's argument list
for d in "${DOMAINS[@]}"; do
  "$DPF" check "$d" --check-handles --check-trademark --json \
    > "/tmp/dpf-batch/$d.json" 2> "/tmp/dpf-batch/$d.err" &
done
wait
```

8 candidates running in parallel typically finish inside 30–60 seconds. Read each JSON with `python3 -c 'import json, sys; ...'` and assemble the [output](#multi-domain-output).

For ad-hoc shortlists (≤16 candidates) parallel runs are fine. For larger lists chunk into batches of 8 to avoid overwhelming Wayback / public APIs.

### Multi-domain output

Produce three sections, in this order:

#### 1. Comparison table

One row per candidate. Columns:

| domain | band | score | top deductions | github | npm | pypi | x/ig | tld notes |

- `band` uses the colour emoji: 🟢 GREEN / 🟡 YELLOW / 🟠 ORANGE / 🔴 RED.
- `top deductions` keeps the 1–2 highest-points entries from `verdict.deductions` (verbatim).
- `github` / `npm` / `pypi` show ✅ for `available`, ❌ for `taken`, ❓ for `unknown`.
- `x/ig` is collapsed because both X and Instagram are bot-walled and frequently `unknown` — render as `❓/❓` unless one of them came back `available` (404), then show the actual symbols.
- `tld notes` flags new gTLDs (`.engineer`, `.app`, etc.) that have a known SEO ramp-up disadvantage even when the band is green.

#### 2. Ranking

Pick the **top 3** candidates by:

1. Verdict band (GREEN > YELLOW > ORANGE > RED).
2. Within band, by `verdict.score` desc.
3. Tie-breaker by handles availability (more ✅ wins).

For each top-3 entry, give:

- 🥇 / 🥈 / 🥉 medal + domain
- 1-line strategic rationale (relate to the user's stated project goals if known)
- 1-line weakness or risk
- handles status summary

#### 3. Top-3 trademark verify checklist

**This is the headline UX of multi-domain mode.** Render only the **top 3** candidates' trademark deeplinks, as a 3×3 markdown table:

| candidate | USPTO | EUIPO | J-PlatPat |
|-----------|-------|-------|-----------|
| **<domain1>** | [search](url) | [search](url) | [search](url) |
| <domain2>     | [search](url) | [search](url) | [search](url) |
| <domain3>     | [search](url) | [search](url) | [search](url) |

The deeplink URLs come straight from the CLI's `trademark.jurisdictions[].deeplink` field — do not reconstruct them by hand.

Tell the user: **trademark verification is manual** (per ADR 0009 — none of the registries publishes a stable public search API). 9 link clicks for the top 3 candidates is the minimum honest verify pass; anything beyond top 3 is over-clicking unless a top-3 entry hits a conflict and the next candidate inherits the slot.

For the **bottom candidates (rank 4+)**, do NOT render their trademark deeplinks. Only flag if the entire top 3 has issues, in which case re-run the verify checklist for ranks 4–6 explicitly when asked.

#### 4. Falsifiable next step

End with one sentence telling the user what to do next: e.g. *"Click the 9 links above; if any USPTO/EUIPO entry returns a hit in class 9 / 33 / 35, the candidate falls out and rank #4 takes its slot."* Make it concrete enough that the user knows when they are done.

## Targeted single-axis checks

When the user only cares about one axis, call the corresponding subcommand directly:

| User intent                             | Run                                    |
| --------------------------------------- | -------------------------------------- |
| "Is the GitHub / npm name free?"        | `"$DPF" handles <domain> --json`       |
| "Does this name look like a typosquat?" | `"$DPF" typosquat <domain> --json`     |
| "Get me the trademark deeplinks."       | `"$DPF" trademark <domain> --jurisdictions us,eu --json` |
| "How does this read in Spanish?"        | `"$DPF" semantics <domain> --languages es --json` |
| "Is this name memorable for voice?"     | `"$DPF" llmo <domain> --json`          |
| "Has this domain been used before?"     | `"$DPF" history <domain> --json`       |
| "Is the structure valid at all?"        | `"$DPF" basic <domain> --json`         |

These can also be batched — same parallel pattern as multi-domain `check`.

## Trademark output (every mode)

Every trademark check returns `status="not_supported"` with a populated `deeplink`. **This is not a bug** — see ADR 0009. The CLI no longer attempts live queries against USPTO / EUIPO / J-PlatPat because none of those registries publishes a stable, documented, no-auth search API.

When summarising:

- Single-domain mode: surface the 3 deeplinks inline (one for each jurisdiction).
- Multi-domain mode: surface the **top-3** candidates' deeplinks in the verify checklist (9 total). Skip ranks 4+.
- Always tell the user trademark verification is **manual** — clicking a deeplink opens the official search UI pre-filled with the SLD.
- Never say "no trademark conflict found" — the CLI cannot determine that.

## Error handling

- **CLI not installed**: tell the user how to install (see install section above).
- **Network error during `--check-handles`**: re-run the same command once before reporting failure; if still failing, surface the unknown entries in the summary as `❓` and note "transport error" inline.
- **Wayback CDX timeout**: a single ReadTimeout is common; for new / freshly-registered domains, "no Wayback snapshots" is the expected outcome anyway. Note the timeout but do not block on it.
- **Domain has obvious syntactic issues** (`-foo-.com`): the `basic` check returns RED with `is_valid_syntax = false`; pass that signal up immediately rather than running the rest.

## Exit-code conventions

`dpf check` exit codes encode the band:
- `0` — GREEN or YELLOW (proceed / proceed with caution)
- `1` — ORANGE (mitigate before proceeding)
- `2` — RED (do not register without manual review)

In a shell script, `if dpf check "$d" --json > out.json; then ...` works because both clean bands return 0. In multi-domain mode, do **not** rely on the per-call exit code to abort early — collect all results, then rank.

## Related docs

- Full CLI walkthrough: `docs/guide/usage.md` in the repo
- Architecture: `docs/architecture.md`
- ADRs: `docs/decisions/` (especially 0009 for trademark)

## Stylistic notes

- Mirror the user's language (English in / English out, 日本語 in / 日本語 out).
- The tool flags candidates, not legal opinions — when surfacing trademark hits, never claim infringement; say "consult counsel" if the user asks for a verdict on the legal angle.
- Treat the LLMO score as one input among many; it is permanently marked experimental.
- Multi-domain output is dense. Resist the urge to add filler explanation between the table, the ranking, and the verify checklist — the user will read them in order, not as one long paragraph.
