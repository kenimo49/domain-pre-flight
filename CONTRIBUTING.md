# Contributing

Thanks for considering a contribution to **domain-pre-flight**.

## TL;DR

- Read `CLAUDE.md` (repository entry point) first — it has the 60-second orientation, design rules, and links to deeper docs.
- Match the existing module shape: each check is `check_<name>(domain) → <Name>Report` with `issues` and `notes` fields.
- Scoring math lives in `score.py`. Don't put deduction values in check modules. (See [ADR 0007](docs/decisions/0007-score-weights-centralised.md).)
- Every change passes `pytest`, `ruff check`, `mypy`, and `bash scripts/smoke.sh --offline`.

## Development setup

```bash
git clone https://github.com/kenimo49/domain-pre-flight
cd domain-pre-flight
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q
ruff check src tests scripts
mypy src/domain_pre_flight
bash scripts/smoke.sh --offline
```

## Where to make changes

| Task | Recipe |
| --- | --- |
| Add a new check | [`docs/agents/extending-checks.md`](docs/agents/extending-checks.md) |
| Add a platform to `dpf handles` | [`docs/agents/adding-platforms.md`](docs/agents/adding-platforms.md) |
| Edit data only (brands, words, TLD risk) | [`docs/agents/data-updates.md`](docs/agents/data-updates.md) |
| Tune scoring weights | [`docs/agents/tuning-scores.md`](docs/agents/tuning-scores.md) |
| Add tests | [`docs/agents/writing-tests.md`](docs/agents/writing-tests.md) |

## Pull requests

- One change per PR. A bug fix and a refactor in the same PR is two PRs.
- Adding a check needs an ADR in `docs/decisions/` only when the design choice is non-obvious. "I wrote check_foo following the existing pattern" does not need an ADR; "I chose Levenshtein over rapidfuzz because…" does.
- Adding a runtime dependency needs a one-sentence justification in the commit message. The default answer is "no, do it without."
- Don't introduce comments that explain WHAT the code does. Only write comments for WHY (constraints, invariants, surprising behaviour).

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

If you've found a vulnerability, please follow the disclosure process in [SECURITY.md](SECURITY.md) — do not file a public issue.
