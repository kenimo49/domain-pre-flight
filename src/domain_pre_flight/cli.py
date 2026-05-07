"""Command-line interface for domain-pre-flight."""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from .checks.basic import check_basic
from .checks.history import check_history
from .checks.score import aggregate

console = Console()


def _band_style(band: str) -> str:
    return {
        "GREEN": "bold green",
        "YELLOW": "bold yellow",
        "ORANGE": "bold dark_orange",
        "RED": "bold red",
    }.get(band, "white")


def _render_verdict(domain: str, basic, history, verdict) -> None:
    console.print(
        f"\n[bold]{domain}[/bold]  →  "
        f"[{_band_style(verdict.band)}]{verdict.band}[/]  "
        f"score=[bold]{verdict.score}[/]/100  — {verdict.summary}\n"
    )

    table = Table(title="Basic checks", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("SLD", basic.sld)
    table.add_row("TLD", basic.tld or "-")
    table.add_row("length / SLD label", f"{basic.length} / {basic.label_length}")
    table.add_row("hyphens / digits", f"{basic.hyphens} / {basic.digits}")
    table.add_row("IDN / punycode", "yes" if basic.has_idn else "no")
    table.add_row("syntax valid", "yes" if basic.is_valid_syntax else "NO")
    table.add_row("TLD risk score", str(basic.tld_risk_score))
    console.print(table)

    if basic.issues:
        console.print("[bold red]Issues:[/]")
        for i in basic.issues:
            console.print(f"  • {i}")
    if basic.notes:
        console.print("[bold]Notes:[/]")
        for n in basic.notes:
            console.print(f"  • {n}")

    if history is not None:
        ht = Table(title="History (Wayback Machine)", show_header=True, header_style="bold")
        ht.add_column("Field")
        ht.add_column("Value")
        ht.add_row("has archive", "yes" if history.has_archive else "no")
        ht.add_row("snapshot count", str(history.snapshot_count))
        ht.add_row("first seen", history.first_seen or "-")
        ht.add_row("last seen", history.last_seen or "-")
        ht.add_row("archive span (days)", str(history.age_days) if history.age_days is not None else "-")
        console.print(ht)
        if history.issues:
            console.print("[bold red]History issues:[/]")
            for i in history.issues:
                console.print(f"  • {i}")
        if history.notes:
            console.print("[bold]History notes:[/]")
            for n in history.notes:
                console.print(f"  • {n}")

    if verdict.deductions:
        dt = Table(title="Score deductions", show_header=True, header_style="bold")
        dt.add_column("Reason")
        dt.add_column("Points", justify="right")
        for reason, points in verdict.deductions:
            dt.add_row(reason, f"-{points}")
        console.print(dt)


def _to_dict(domain, basic, history, verdict) -> dict:
    return {
        "domain": domain,
        "verdict": {
            "score": verdict.score,
            "band": verdict.band,
            "summary": verdict.summary,
            "deductions": [{"reason": r, "points": p} for r, p in verdict.deductions],
        },
        "basic": {
            "sld": basic.sld,
            "tld": basic.tld,
            "length": basic.length,
            "label_length": basic.label_length,
            "hyphens": basic.hyphens,
            "digits": basic.digits,
            "has_idn": basic.has_idn,
            "is_valid_syntax": basic.is_valid_syntax,
            "tld_risk_score": basic.tld_risk_score,
            "issues": basic.issues,
            "notes": basic.notes,
        },
        "history": (
            None
            if history is None
            else {
                "has_archive": history.has_archive,
                "snapshot_count": history.snapshot_count,
                "first_seen": history.first_seen,
                "last_seen": history.last_seen,
                "age_days": history.age_days,
                "issues": history.issues,
                "notes": history.notes,
            }
        ),
    }


@click.group(invoke_without_command=True)
@click.version_option(package_name="domain-pre-flight")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Pre-flight checks before registering a domain."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("domain")
@click.option(
    "--no-history",
    is_flag=True,
    default=False,
    help="Skip Wayback Machine history lookup (offline-only run).",
)
@click.option(
    "--enable-backlinks",
    is_flag=True,
    default=False,
    help="(ROADMAP — not yet implemented) Enable detailed backlink evaluation. Requires paid API keys via env vars; opt-in.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output JSON instead of a rich table.",
)
def check(domain: str, no_history: bool, enable_backlinks: bool, as_json: bool) -> None:
    """Run all enabled checks on DOMAIN and emit a verdict."""
    if enable_backlinks:
        click.echo(
            "warning: --enable-backlinks is reserved for a future release; ignored for now.",
            err=True,
        )

    basic = check_basic(domain)
    history = None if no_history else check_history(domain)
    verdict = aggregate(basic, history)

    if as_json:
        click.echo(json.dumps(_to_dict(domain, basic, history, verdict), ensure_ascii=False, indent=2))
    else:
        _render_verdict(domain, basic, history, verdict)

    # Exit code 0 GREEN/YELLOW, 1 ORANGE, 2 RED — useful for CI gating.
    sys.exit({"GREEN": 0, "YELLOW": 0, "ORANGE": 1, "RED": 2}[verdict.band])


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output JSON.")
def history(domain: str, as_json: bool) -> None:
    """Show only the Wayback Machine history for DOMAIN."""
    h = check_history(domain)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "domain": h.domain,
                    "has_archive": h.has_archive,
                    "snapshot_count": h.snapshot_count,
                    "first_seen": h.first_seen,
                    "last_seen": h.last_seen,
                    "age_days": h.age_days,
                    "issues": h.issues,
                    "notes": h.notes,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    console.print(f"\n[bold]{h.domain}[/]  archived={h.has_archive}  snapshots={h.snapshot_count}")
    console.print(f"first_seen={h.first_seen}  last_seen={h.last_seen}  span_days={h.age_days}")
    for n in h.notes:
        console.print(f"  • {n}")
    for i in h.issues:
        console.print(f"  ! {i}")


@main.command()
@click.argument("domain")
def basic(domain: str) -> None:
    """Run only offline structural checks on DOMAIN."""
    b = check_basic(domain)
    console.print(
        f"\n[bold]{b.domain}[/]  sld={b.sld}  tld={b.tld}  "
        f"len={b.length}  hyphens={b.hyphens}  digits={b.digits}  "
        f"idn={'yes' if b.has_idn else 'no'}  tld_risk={b.tld_risk_score}"
    )
    for n in b.notes:
        console.print(f"  • {n}")
    for i in b.issues:
        console.print(f"  ! {i}")


if __name__ == "__main__":
    main()
