# Recipe: Writing tests in the project's pattern

The repo has 74 tests across 8 files. They follow a small set of patterns; matching the pattern keeps the test suite easy to read and easy to extend.

## File naming

`tests/test_<module>.py` mirrors `src/domain_pre_flight/checks/<module>.py`. One test file per check module is the rule.

Cross-cutting tests (e.g. score integration, the verdict shape) live in `tests/test_score.py`.

## Test patterns by check kind

### Offline check, bundled-data driven (typosquat, semantics, llmo, basic)

Pattern: pytest cases with no fixtures. Pass an explicit input to the check function and assert on the report.

```python
def test_clean_name_no_match():
    r = check_typosquat("nicebrand.com")
    assert r.matches == []
    assert r.issues == []
```

Required cases for any offline check:

- One clean / no-match input
- One positive case per kind of signal the module emits
- Invalid input (`.` or `""`) — must return an empty report with a `notes` entry, never raise
- Score-integration case in `test_score.py` showing the band drops appropriately

Use `brands=[...]` / `languages=[...]` style explicit-list arguments to **isolate** tests from the bundled data. A test that says "given this list" is more stable than one that depends on what is currently in `data/`.

### HTTP-based check (handles, history, trademark)

Pattern: `responses` library to mock HTTP. Decorate each test with `@responses.activate`. Add the expected request, assert on the report.

```python
@responses.activate
def test_github_taken():
    responses.add(responses.GET, "https://api.github.com/users/foo", status=200)
    r = check_github("foo")
    assert r.status == "taken"
```

Required cases for any HTTP check:

- The success path (taken / found / 200)
- The not-found path (available / 404)
- A rate-limit / 503 / 429 path → must return `unknown` / `lookup_failed` with a useful `detail`
- A transport-error path (use `monkeypatch.setattr(...requests..., boom)`) → must return the same `unknown`-equivalent shape, never raise
- A `--json`-style payload assertion if the report shape is non-trivial

Never let a test depend on the real network. CI must not be allowed to fail because GitHub returned a 502.

### Score integration

Pattern: build minimal stub reports, call `aggregate(...)`, assert on the resulting band/score.

```python
def test_high_risk_tld_drops_band():
    v = aggregate(check_basic("foobar.tk"), HistoryReport(domain="foobar.tk"))
    assert v.band in {Band.ORANGE, Band.RED}
```

`HistoryReport(domain="x")` works because `HistoryReport` has sensible defaults. The same pattern works for any of the report dataclasses.

## What good test names look like

- `test_<thing>_<expected_outcome>` — `test_handles_full_fanout`, `test_clean_com_is_green`
- `test_<edge_case>_returns_<state>` — `test_check_handles_unknown_platform_noted`

Resist long sentence-style names; they signal that one test is doing too much.

## What to **avoid**

- **Asserting on exact strings the renderer emits.** The CLI rendering is presentation; assert on the dataclass shape instead.
- **Loading bundled data inside a test that should be hermetic.** Pass an explicit list (`brands=[...]`, `languages=[...]`) instead.
- **Marking tests as `@pytest.mark.skip` because of network.** If a test needs the network, it should not be in CI. Mock with `responses` or remove the test.
- **Catching `pytest.raises(Exception)`.** Be specific. Catch `ValueError`, `requests.RequestException`, etc.
- **Comparing floats without tolerance.** Use `pytest.approx(...)` if a float lands somewhere.

## Running tests

```bash
pytest -q                                  # everything
pytest -q tests/test_handles.py            # one file
pytest -q tests/test_handles.py::test_github_taken   # one case
pytest -q -k "trademark and not unknown"   # filter
```

CI runs `pytest -q` plus `bash scripts/smoke.sh --offline` against Python 3.10/3.11/3.12. Match those locally before pushing.
