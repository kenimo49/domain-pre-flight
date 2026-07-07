# Subprocess-variant MCP server (for comparison only)

This directory contains a deliberately naive MCP server that wraps the
`domain-pre-flight` CLI via `subprocess` instead of importing the check
functions as a library.

**Do not use this in production.** The supported server is the
library-direct one that ships with the package:

```bash
pip install "domain-pre-flight[mcp]"
claude mcp add domain-pre-flight -- domain-pre-flight-mcp
```

This variant exists as the "before" half of a before/after comparison
(latency, security surface, output quality) written up in the companion
article. It is the shape you get when you MCP-wrap *someone else's* CLI
that you cannot import as a library.

## What it demonstrates

| Aspect | Subprocess variant | Library-direct |
| ------ | ------------------ | -------------- |
| Startup cost per call | Python interpreter + import per invocation | none |
| Security surface | argv construction (see comments in `server.py`) | none |
| Output | text/JSON re-parsed from stdout | structured dict, single source of truth |
| Coupling | CLI flags are the API | function signatures are the API |

## Run it

```bash
pip install "domain-pre-flight[mcp]"   # needs the CLI on PATH + mcp SDK
python examples/subprocess-variant/server.py
```
