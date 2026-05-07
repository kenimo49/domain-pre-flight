# Context card: `cli.py`

**Path**: `src/domain_pre_flight/cli.py`
**Test**: covered indirectly via `scripts/smoke.sh`. A future `tests/test_cli.py` using Click's `CliRunner` is on the wish list.

## Responsibility

Click entry point. Owns subcommand registration, JSON / rich rendering, and the score → exit-code mapping. **No domain logic.**

## Public surface

```bash
dpf check <domain> [--no-history] [--check-handles] [--no-typosquat]
                   [--check-trademark] [--trademark-jurisdictions ...]
                   [--no-semantics] [--languages ...] [--no-llmo] [--json]
dpf basic <domain> [--json]
dpf history <domain> [--json]
dpf handles <domain> [--platforms ...] [--json]
dpf typosquat <domain> [--json]
dpf trademark <domain> [--jurisdictions ...] [--json]
dpf semantics <domain> [--languages ...] [--json]
dpf llmo <domain> [--json]
```

## Dependencies

- `click`
- `rich`
- All eight check modules + `score.py`

## Conventions / invariants

- Entry point is `main()` registered as both `domain-pre-flight` and `dpf` in `pyproject.toml`.
- Every subcommand returns the relevant report dataclass(es) and chooses one of two output paths via `--json`:
  - `--json`: build a payload with `dataclasses.asdict` (or `_payload` for `dpf check`), emit via `json.dumps(..., ensure_ascii=False, indent=2)`.
  - default: rich tables via the `_*_table` helpers + `_emit_lines` for issues/notes.
- `dpf check` exits with `sys.exit(EXIT_CODES[verdict.band])`. All other subcommands exit 0.
- All `--check-X` flags are opt-in (default-off). All `--no-X` flags are opt-out (default-on). Don't mix.
- The `_render_verdict` helper renders sections in this order: basic → history → handles → typosquat → trademark → semantics → llmo → score deductions. Match this order if you add a new section.

## Rendering helpers

| Helper                  | Renders                                            |
| ----------------------- | -------------------------------------------------- |
| `_basic_table`          | Basic check fields                                 |
| `_history_table`        | Wayback summary                                    |
| `_handles_table`        | Per-platform handle status with status colour     |
| `_typosquat_table`      | Brand match list (top 10)                          |
| `_trademark_table`      | Per-jurisdiction status + match counts + deeplink |
| `_semantics_table`      | Per-language matches (top 10)                      |
| `_llmo_table`           | Per-axis scores + total + band                     |
| `_emit_lines`           | Bullet list with optional style prefix             |

## JSON payload shape (`dpf check --json`)

```json
{
  "domain": "...",
  "verdict": { "score": int, "band": "...", "summary": "...", "deductions": [...] },
  "basic":     { ... } | null,
  "history":   { ... } | null,
  "handles":   { ... } | null,
  "typosquat": { ... } | null,
  "trademark": { ... } | null,
  "semantics": { ... } | null,
  "llmo":      { ... } | null
}
```

`null` indicates the corresponding check was disabled or skipped.

## Common edits

| Change                              | Touch                                          |
| ----------------------------------- | ---------------------------------------------- |
| Add a flag to `dpf check`           | A `@click.option(...)` on `check`, plumb to `aggregate` and `_payload` |
| Add a new top-level subcommand      | New `@main.command()` function + helper table renderer |
| Change colour / formatting          | `_BAND_STYLES`, `_HANDLE_STATUS_STYLES`, or per-table style |
| Update the JSON payload shape       | `_payload` (and bump README / usage guide)     |

## Anti-patterns specific to this module

- Putting domain logic in `cli.py`. If a function is testable without `CliRunner`, it does not belong here.
- Adding both `--check-X` and `--no-X` for the same check. Pick one based on whether the check is fast enough to be default-on.
- Hard-coding ANSI colours. Use `rich`'s style names so themes work.
- Forgetting to register a new section in `_render_verdict` AND `_payload`. Both are mandatory.
