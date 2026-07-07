"""Subprocess-variant MCP server — comparison baseline, not for production use.

Wraps the `domain-pre-flight` CLI with subprocess calls. See README.md in
this directory for why this exists and what it is compared against.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("domain-pre-flight-subprocess")

# 30s: `check` includes network lookups (Wayback); a hung child must not
# hang the MCP session.
_TIMEOUT_SECONDS = 30


def _run_cli(args: list[str]) -> dict[str, Any]:
    # Args are passed as a list and shell=False (the default): the domain
    # string can never be interpreted by a shell. The tempting one-liner
    #   subprocess.run(f"dpf check {domain} --json", shell=True)
    # would make `example.com; rm -rf ~` a valid "domain".
    proc = subprocess.run(  # noqa: S603
        ["domain-pre-flight", *args, "--json"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
    )
    # `dpf check` exits non-zero for YELLOW/ORANGE/RED bands by design, so a
    # non-zero exit code is not an error. Empty stdout is.
    if not proc.stdout.strip():
        return {"error": "CLI produced no output", "stderr": proc.stderr[-500:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "CLI output was not valid JSON", "stdout": proc.stdout[:500]}


@mcp.tool()
def check_domain(
    domain: str,
    include_handles: bool = False,
    include_trademark: bool = False,
    include_rdap: bool = False,
    include_dns: bool = False,
) -> dict[str, Any]:
    """Run pre-flight safety checks on a domain candidate before registering it.

    Returns a verdict (score 0-100, band GREEN/YELLOW/ORANGE/RED) plus section
    reports. Same contract as the library-direct server, implemented by
    shelling out to the `domain-pre-flight` CLI.
    """
    args = ["check", domain]
    if include_handles:
        args.append("--check-handles")
    if include_trademark:
        args.append("--check-trademark")
    if include_rdap:
        args.append("--check-rdap")
    if include_dns:
        args.append("--check-dns")
    return _run_cli(args)


@mcp.tool()
def check_handles(domain: str, platforms: list[str] | None = None) -> dict[str, Any]:
    """Check same-name handle availability on GitHub / npm / PyPI / X / Instagram."""
    args = ["handles", domain]
    if platforms:
        args += ["--platforms", ",".join(platforms)]
    return _run_cli(args)


@mcp.tool()
def check_trademark(domain: str, jurisdictions: list[str] | None = None) -> dict[str, Any]:
    """Search USPTO / EUIPO trademark registries for marks matching the name."""
    args = ["trademark", domain]
    if jurisdictions:
        args += ["--jurisdictions", ",".join(jurisdictions)]
    return _run_cli(args)


@mcp.tool()
def list_typo_permutations(
    domain: str, kind: str | None = None, limit: int = 50
) -> dict[str, Any]:
    """Generate dnstwist-style typo/spoof permutations of the domain's name."""
    args = ["permutations", domain, "--limit", str(limit)]
    if kind:
        args += ["--kind", kind]
    return _run_cli(args)


if __name__ == "__main__":
    mcp.run()
