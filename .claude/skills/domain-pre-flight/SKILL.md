---
name: domain-pre-flight
description: Pre-flight checks before registering a domain for a new site or app. Runs structural / history / typosquat / multi-language / LLMO checks against the candidate, optionally adds same-name handle availability and trademark conflict queries, and returns a single verdict band (GREEN / YELLOW / ORANGE / RED) with itemised reasons. Use when the user is choosing a domain, evaluating a candidate from a brainstorm list, or wants a sanity check before pulling the trigger on a registrar.
argument-hint: <domain> [--full] [--handles] [--trademark]
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
2. **Run the right `dpf check` invocation** based on the user's intent (see the modes below). Always pass `--json` and parse with `python3 -c 'import json, sys; ...'` so you do not have to read coloured terminal output.
3. **Summarise the verdict** in 3–6 lines. Lead with the band + score; follow with the *reasons* the score landed there (the `verdict.deductions` list).
4. **Recommend the next step** — register, walk away, or run a deeper check (handles / trademark).

## Install (only if `$DPF` did not resolve)

```bash
# Recommended — pipx isolates the CLI in its own venv but exposes `dpf` on PATH
pipx install git+https://github.com/kenimo49/domain-pre-flight.git

# Or, from a local clone in editable mode
pip install -e /home/iris/repos/domain-pre-flight
```

## Modes

### Default (fast, offline + Wayback)

```bash
dpf check <domain> --json
```

Runs basic + history + typosquat + semantics + llmo. ~1 second. Use this for a "quick look" check.

### Full pre-flight (includes paid-API-equivalent checks)

```bash
dpf check <domain> --check-handles --check-trademark --json
```

Adds same-name handle availability across GitHub / npm / PyPI / X / Instagram, plus USPTO + EUIPO trademark queries (J-PlatPat surfaces a deeplink). ~10 seconds. Use this when the user is about to commit to a real product launch.

### Targeted single-axis checks

When the user only cares about one axis, call the corresponding subcommand directly:

| User intent                             | Run                                    |
| --------------------------------------- | -------------------------------------- |
| "Is the GitHub / npm name free?"        | `dpf handles <domain> --json`          |
| "Does this name look like a typosquat?" | `dpf typosquat <domain> --json`        |
| "Does this hit a US/EU trademark?"      | `dpf trademark <domain> --jurisdictions us,eu --json` |
| "How does this read in Spanish?"        | `dpf semantics <domain> --languages es --json` |
| "Is this name memorable for voice?"     | `dpf llmo <domain> --json`             |
| "Has this domain been used before?"     | `dpf history <domain> --json`          |
| "Is the structure valid at all?"        | `dpf basic <domain> --json`            |

## Output format

After parsing the JSON, summarise like this:

```
**<domain>**: <band> — score <N>/100

What flagged:
- <deduction reason 1>: -<points>
- <deduction reason 2>: -<points>

Recommendation: <one sentence — register, walk away, or run a deeper check>
```

Keep the report under ~6 lines unless the user asks for the full breakdown. The deductions list in JSON is the source of truth — quote it directly rather than summarising in your own words (the wording is calibrated).

If a check returned `lookup_failed` or `unknown` (e.g. trademark API hiccup, X bot wall), say so explicitly. Do not pretend you got a clean answer.

## Error handling

- **CLI not installed**: tell the user how to install (`pip install -e /home/iris/repos/domain-pre-flight` from a clone, or `pip install git+https://github.com/kenimo49/domain-pre-flight.git`).
- **Network error during `--check-handles` / `--check-trademark`**: re-run the same command once before reporting failure; if still failing, surface the lookup_failed entries in the summary.
- **Domain has obvious syntactic issues** (`-foo-.com`): the `basic` check will return RED with `is_valid_syntax = false`; pass that signal up immediately rather than running the rest.

## Exit-code conventions

`dpf check` exit codes encode the band:
- `0` — GREEN or YELLOW (proceed / proceed with caution)
- `1` — ORANGE (mitigate before proceeding)
- `2` — RED (do not register without manual review)

In a shell script, `if dpf check "$d" --json > out.json; then ...` works because both clean bands return 0.

## Related docs

- Full CLI walkthrough: `docs/guide/usage.md` in the repo
- Architecture: `docs/architecture.md`
- ADRs: `docs/decisions/`

## Stylistic notes

- Mirror the user's language (English in / English out, 日本語 in / 日本語 out).
- The tool flags candidates, not legal opinions — when surfacing trademark hits, never claim infringement; say "consult counsel" if the user asks for a verdict on the legal angle.
- Treat the LLMO score as one input among many; it is permanently marked experimental.
