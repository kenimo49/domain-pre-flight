---
name: Bug report
about: Something is wrong with the CLI or a check
title: "[bug] "
labels: bug
---

## What happened

A clear, single-paragraph description of the actual behaviour.

## What I expected

What the docs or your intuition said *should* have happened.

## Reproduction

```bash
# the exact CLI invocation
dpf check ...
```

If the bug is data-driven (a specific domain trips a wrong band, a brand list miss, etc.), include the domain.

## Output

The relevant stdout / JSON. If the report is large, paste the `verdict.deductions` array and the offending check section only.

## Environment

- domain-pre-flight version: `dpf --version`
- Python: `python --version`
- OS:
- Install method: `pipx install` / `pip install -e` / other
