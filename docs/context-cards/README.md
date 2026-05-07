# Context cards

Each card under this directory is a **minimum-viable context** for editing one specific module. They are built for AI coding agents that need to make a focused change without loading the whole repo into context.

Pick a card based on the module you intend to edit. The card lists:

- the file path
- the module's responsibility (one paragraph)
- its public API
- its dependencies (in-repo and external)
- the conventions / invariants the module follows
- the test file you must keep green
- the data files (if any) the module consumes

Each card is kept under ~200 lines so loading one card costs a small, predictable slice of context.

## Cards

| Module                 | Card                                       | When to load                            |
| ---------------------- | ------------------------------------------ | --------------------------------------- |
| `checks/basic.py`      | [`checks-basic.md`](checks-basic.md)       | Editing structural checks or TLD risk   |
| `checks/history.py`    | [`checks-history.md`](checks-history.md)   | Editing Wayback queries                 |
| `checks/handles.py`    | [`checks-handles.md`](checks-handles.md)   | Adding a platform or tweaking handles   |
| `checks/typosquat.py`  | [`checks-typosquat.md`](checks-typosquat.md) | Editing brand-similarity logic         |
| `checks/trademark.py`  | [`checks-trademark.md`](checks-trademark.md) | Editing USPTO/EUIPO/J-PlatPat queries  |
| `checks/semantics.py`  | [`checks-semantics.md`](checks-semantics.md) | Editing the multi-language scan        |
| `checks/llmo.py`       | [`checks-llmo.md`](checks-llmo.md)         | Editing LLMO heuristics                 |
| `checks/score.py`      | [`checks-score.md`](checks-score.md)       | Editing weights or band thresholds      |
| `cli.py`               | [`cli.md`](cli.md)                         | Editing CLI flags or rendering          |

## How to use a card with an AI agent

1. Load `CLAUDE.md` (the repo map) — always.
2. Load the relevant card from this directory.
3. Load only the *test file* mentioned by the card.
4. Make the change. Run the named test. Run smoke. Done.

If the change spans two modules, load both cards. If it spans three, you are probably violating the layering — read `docs/architecture.md` first.
