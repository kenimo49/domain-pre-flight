# Recipe: Extending the tool with a new check

Use this recipe when you want a whole new axis of evaluation, not a tweak to an existing one. Examples that fit: DNSSEC presence, MX-record sanity, registrar reputation, expiry / WHOIS age, certificate transparency log presence.

## Preconditions

- Read `CLAUDE.md` and `docs/architecture.md` first.
- Confirm the check belongs in this repo. Out-of-scope: domain valuation, drop-catching, marketing intelligence.
- Decide whether the check is **fast-and-default** (offline or single cheap HTTP call) or **slow-and-opt-in** (multiple HTTP calls, heavy I/O, paid API).

## Steps

### 1. Create the check module

`src/domain_pre_flight/checks/<name>.py`. Mirror the shape of an existing module — `typosquat.py` for offline heuristics, `handles.py` for parallel HTTP, `trademark.py` for opt-in heavy network.

Required exports:

```python
@dataclass
class <Name>Report:
    domain: str
    sld: str
    # … fields …
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def check_<name>(domain: str, ...) -> <Name>Report:
    from .basic import parse_domain  # avoid import cycle
    domain = domain.strip().lower().rstrip(".")
    sld, _ = parse_domain(domain)
    report = <Name>Report(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — <name> check skipped")
        return report

    # … real work …

    return report
```

Rules:

- The module owns **no scoring math**. It surfaces facts and human-readable hints in `issues` / `notes`.
- The `check_<name>(domain: str, ...)` signature is non-negotiable. First positional arg is `domain`; everything else is keyword-only.
- Network calls catch `requests.RequestException` and surface the failure on the report; never raise.
- Parallel HTTP uses `concurrent.futures.ThreadPoolExecutor`. Match the pattern in `handles.py`.

### 2. Wire scoring into `score.py`

```python
def _<name>_deductions(report: <Name>Report) -> list[tuple[str, int]]:
    if not report.matches:        # or whatever indicates "nothing to flag"
        return []
    # decide deductions, return [(reason_string, points), ...]
    return [("...", 30)]
```

Then extend `aggregate(...)`:

```python
def aggregate(
    basic: BasicReport,
    history: HistoryReport | None = None,
    typosquat: TyposquatReport | None = None,
    trademark: TrademarkReport | None = None,
    semantics: SemanticsReport | None = None,
    llmo: LlmoReport | None = None,
    <name>: <Name>Report | None = None,        # add this
) -> Verdict:
    # ...
    if <name> is not None:
        deductions.extend(_<name>_deductions(<name>))
```

Rules:

- Weights live here and **only here**. Auditing all weights = reading one file.
- Pick weights conservatively. Start lower than your gut says; tune up only with calibration evidence.
- A check that returns no signal must produce zero deductions, never a small "background" deduction.

### 3. Add CLI surface in `cli.py`

Three things:

#### 3a. Top-level subcommand for the check in isolation

```python
@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def <name>(domain: str, as_json: bool) -> None:
    """One-line description of the check."""
    r = check_<name>(domain)
    if as_json:
        _emit_json({"domain": r.domain, "<name>": asdict(r)})
        return
    console.print(_<name>_table(r))
    _emit_lines("Issues", r.issues, style="bold red")
    _emit_lines("Notes", r.notes, style="bold")
```

#### 3b. Flag on `dpf check`

For a fast/default check use `--no-<name>` (default-on); for slow/opt-in use `--check-<name>` (default-off). Don't add both.

#### 3c. Rendering helper

```python
def _<name>_table(r: <Name>Report) -> Table:
    table = Table(title=f"... '{r.sld}'", show_header=True, header_style="bold")
    # add columns + rows
    return table
```

Wire the helper into `_render_verdict` (between the existing checks, in the order you want it displayed).

#### 3d. Update `_payload` to include the new report

```python
"<name>": None if <name> is None else asdict(<name>),
```

### 4. Tests

Mirror the closest existing test file:

- Offline check + bundled data: copy `tests/test_typosquat.py`.
- HTTP-based check: copy `tests/test_handles.py` (uses `responses`).
- Multi-source HTTP: copy `tests/test_trademark.py`.

Required cases:

- A clean / no-match input
- At least one positive case per signal kind the module produces
- Invalid input (`.` / empty)
- Network failure path (if applicable) — must produce a report with `lookup_failed`-equivalent state, not raise
- Score integration: a case where the verdict band drops because of this check

### 5. Smoke

Add at least one fixture case to `scripts/smoke.sh`:

```bash
"new-fixture-domain.com|YELLOW|0"
```

Pick a fixture whose verdict the new check directly drives. Keep `--offline` runnable in CI.

### 6. Documentation

In this order:

1. README: add a row to the "What v0.x does" table.
2. `docs/guide/usage.md`: add a `dpf <name>` subsection following the existing template.
3. `docs/architecture.md`: extend the module-by-module section.
4. `docs/decisions/`: write an ADR if the design choice is non-obvious (anything beyond "yes I added the obvious check").
5. `docs/context-cards/checks-<name>.md`: a minimal context card for future agents who only edit your new module.

### 7. Validate end-to-end

```bash
pytest -q
bash scripts/smoke.sh --offline
.venv/bin/dpf check example.com           # rendered output looks right
.venv/bin/dpf <name> example.com --json   # JSON shape matches existing checks
```

If `pytest` and smoke pass and the rendered JSON has the same shape as siblings, the check is integrated correctly.

## Common mistakes

- **Putting deductions in the check module.** Symptom: `score.py` looks short and "nothing to do" when adding the integration. Fix: move the scoring math out.
- **Returning raw API objects in the report.** Symptom: `asdict(report)` blows up because some field isn't a dataclass / primitive. Fix: extract only the primitives you need into the report.
- **Forgetting to wire `_payload`.** Symptom: `dpf check --json` works, but the new section is missing from the JSON. Fix: add the field to `_payload` AND `_render_verdict`.
- **A new flag mismatching the convention.** Symptom: PR review pushback. Fix: pick `--no-<name>` for default-on or `--check-<name>` for default-off — never both.
- **Importing across check modules.** Symptom: circular import or a check module pulling in something it doesn't need. Fix: cross-module coordination only via `cli.py` and `score.py`.
