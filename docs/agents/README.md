# Agents directory

Recipes optimised for AI coding agents (Claude Code, Cursor, etc.) and human contributors who want to extend the tool without re-discovering the same constraints we already discovered.

| Recipe                                                  | When to use                                          |
| ------------------------------------------------------- | ---------------------------------------------------- |
| [`extending-checks.md`](extending-checks.md)            | Add a brand-new check (e.g. DNSSEC, MX, expiry)      |
| [`adding-platforms.md`](adding-platforms.md)            | Add a new platform to the handle check               |
| [`data-updates.md`](data-updates.md)                    | Edit only the bundled data (brand list, word lists, TLD JSON) |
| [`tuning-scores.md`](tuning-scores.md)                  | Adjust deduction weights or score band thresholds    |
| [`writing-tests.md`](writing-tests.md)                  | Add tests in the project's existing patterns         |

All recipes assume you have read [`../../CLAUDE.md`](../../CLAUDE.md) and [`../architecture.md`](../architecture.md). The recipes deliberately do *not* re-explain what the tool does — they explain how to make a specific kind of change without breaking the layering.
