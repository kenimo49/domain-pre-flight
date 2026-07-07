"""MCP server exposing domain-pre-flight checks as tools.

Library-direct variant: imports the check functions instead of shelling out
to the CLI, so tools return structured data with no subprocess overhead.
Run via `domain-pre-flight-mcp` (stdio transport).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "The MCP server requires the 'mcp' extra: pip install 'domain-pre-flight[mcp]'"
    ) from e

from .checks.basic import check_basic
from .checks.dns_sanity import check_dns_sanity
from .checks.handles import check_handles as _check_handles
from .checks.history import check_history
from .checks.idn_homograph import check_idn_homograph
from .checks.llmo import check_llmo
from .checks.permutations import generate_permutations
from .checks.rdap import check_rdap
from .checks.score import aggregate
from .checks.semantics import check_semantics
from .checks.trademark import check_trademark as _check_trademark
from .checks.typosquat import check_typosquat
from .cli import CheckResults, _payload

mcp = FastMCP("domain-pre-flight")


@mcp.tool()
def check_domain(
    domain: str,
    include_handles: bool = False,
    include_trademark: bool = False,
    include_rdap: bool = False,
    include_dns: bool = False,
) -> dict[str, Any]:
    """Run pre-flight safety checks on a domain candidate BEFORE registering it.

    Answers "is this name safe to register?" with a verdict (score 0-100, band
    GREEN/YELLOW/ORANGE/RED, summary, per-deduction reasons) plus section
    reports: structural checks and TLD risk, Wayback Machine history, typosquat
    / brand similarity, negative meanings across major languages, pronunciation
    and memorability fitness, and IDN homograph detection.

    Slower checks are off by default; enable per call: include_handles (GitHub /
    npm / PyPI / X / Instagram same-name availability), include_trademark
    (USPTO / EUIPO registries), include_rdap (domain age, expiry, registrar),
    include_dns (MX / SPF / DMARC / DKIM hygiene, useful for aftermarket buys).

    To compare several candidates, call this tool once per candidate.
    """
    results = CheckResults(
        basic=check_basic(domain),
        history=check_history(domain),
        handles=_check_handles(domain) if include_handles else None,
        typosquat=check_typosquat(domain),
        trademark=_check_trademark(domain) if include_trademark else None,
        semantics=check_semantics(domain),
        llmo=check_llmo(domain),
        homograph=check_idn_homograph(domain),
        rdap=check_rdap(domain) if include_rdap else None,
        dns_sanity=check_dns_sanity(domain) if include_dns else None,
    )
    verdict = aggregate(
        results.basic,
        results.history,
        results.typosquat,
        results.trademark,
        results.semantics,
        results.llmo,
        results.homograph,
        results.rdap,
        results.dns_sanity,
    )
    return _payload(domain, results, verdict)


@mcp.tool()
def check_handles(domain: str, platforms: list[str] | None = None) -> dict[str, Any]:
    """Check same-name handle availability across developer platforms.

    Given a domain (or bare name), reports whether the second-level name is
    taken, available, or unknown on GitHub, npm, PyPI, X/Twitter, and
    Instagram. Pass `platforms` to restrict the lookup (e.g. ["github",
    "npm"]). Useful when a project wants the same name everywhere.
    """
    return asdict(_check_handles(domain, platforms=platforms))


@mcp.tool()
def check_trademark(domain: str, jurisdictions: list[str] | None = None) -> dict[str, Any]:
    """Search trademark registries for marks matching the domain's name.

    Queries USPTO and EUIPO (TMview) for exact and contains matches; J-PlatPat
    is surfaced as a deeplink for manual verification. Default jurisdictions:
    us, eu, jp. This is a mechanical pre-screen only — it does NOT assess
    phonetic similarity or likelihood of confusion, and is not legal advice.
    """
    return asdict(_check_trademark(domain, jurisdictions=jurisdictions))


@mcp.tool()
def list_typo_permutations(
    domain: str, kind: str | None = None, limit: int = 50
) -> dict[str, Any]:
    """Generate dnstwist-style typo and spoof permutations of a domain's name.

    Returns candidate look-alike names (omission, substitution, transposition,
    homoglyph, ...) an attacker could register. Use it to decide defensive
    registrations or to eyeball how typo-prone a candidate name is. Filter by
    `kind`; `limit` caps the list (default 50).
    """
    report = generate_permutations(domain)
    permutations = report.permutations
    if kind:
        permutations = [p for p in permutations if p.kind == kind]
    return {
        "domain": report.base_domain,
        "sld": report.sld,
        "total": len(permutations),
        "permutations": [asdict(p) for p in permutations[:limit]],
        "notes": report.notes,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
