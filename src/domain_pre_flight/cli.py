"""Command-line interface for domain-pre-flight."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .checks.basic import BasicReport, check_basic
from .checks.handles import HandleReport, check_handles
from .checks.history import HistoryReport, check_history
from .checks.idn_homograph import HomographReport, check_idn_homograph
from .checks.llmo import LlmoReport, check_llmo
from .checks.score import EXIT_CODES, Band, Verdict, aggregate
from .checks.semantics import SUPPORTED_LANGUAGES, SemanticsReport, check_semantics
from .checks.trademark import TrademarkReport, check_trademark
from .checks.typosquat import TyposquatReport, check_typosquat

_HANDLE_STATUS_STYLES = {
    "taken": "bold red",
    "available": "bold green",
    "unknown": "bold yellow",
}

console = Console()

_BAND_STYLES: dict[Band, str] = {
    Band.GREEN: "bold green",
    Band.YELLOW: "bold yellow",
    Band.ORANGE: "bold dark_orange",
    Band.RED: "bold red",
}


def _emit_lines(prefix_label: str, lines: list[str], style: str = "") -> None:
    if not lines:
        return
    label = f"[{style}]{prefix_label}:[/]" if style else f"{prefix_label}:"
    console.print(label)
    for line in lines:
        console.print(f"  • {line}")


def _basic_table(basic: BasicReport) -> Table:
    table = Table(title="Basic checks", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("SLD", basic.sld)
    table.add_row("TLD", basic.tld or "-")
    table.add_row("length / SLD label", f"{basic.length} / {basic.label_length}")
    table.add_row("hyphens / digits", f"{basic.hyphens} / {basic.digits}")
    table.add_row("IDN / punycode", "yes" if basic.has_idn else "no")
    table.add_row("syntax valid", "yes" if basic.is_valid_syntax else "NO")
    return table


def _homograph_table(report: HomographReport) -> Table:
    table = Table(title=f"IDN homograph for '{report.sld}'", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("is IDN", "yes" if report.is_idn else "no")
    table.add_row("has confusables", "yes" if report.has_confusables else "no")
    table.add_row("de-confused form", report.de_confused or "-")
    table.add_row("brand collision", report.brand_collision or "-")
    table.add_row("severity", report.severity)
    return table


def _llmo_table(llmo: LlmoReport) -> Table:
    table = Table(title=f"LLMO fitness for '{llmo.sld}' (experimental)", show_header=True, header_style="bold")
    table.add_column("Axis")
    table.add_column("Score", justify="right")
    table.add_row("cluster (consonant runs)", f"{llmo.cluster_score}/5")
    table.add_row("vowel (ratio)", f"{llmo.vowel_score}/5")
    table.add_row("length (4-9 chars optimal)", f"{llmo.length_score}/5")
    table.add_row("repeats (no long runs)", f"{llmo.repeats_score}/5")
    table.add_row("[bold]total[/]", f"[bold]{llmo.fitness}/20 ({llmo.band})[/]")
    return table


def _semantics_table(sem: SemanticsReport) -> Table:
    table = Table(title=f"Negative-meaning scan for '{sem.sld}'", show_header=True, header_style="bold")
    table.add_column("Language")
    table.add_column("Term")
    table.add_column("Severity")
    table.add_column("Kind")
    if not sem.matches:
        table.add_row("(none)", "-", "-", "-")
    for m in sem.matches[:10]:
        table.add_row(m.language, m.term, m.severity, m.kind)
    return table


def _trademark_table(tm: TrademarkReport) -> Table:
    table = Table(title=f"Trademark search for '{tm.sld}'", show_header=True, header_style="bold")
    table.add_column("Jurisdiction")
    table.add_column("Status")
    table.add_column("Matches")
    table.add_column("Deeplink")
    for j in tm.jurisdictions:
        status_text = j.status if not j.detail else f"{j.status} ({j.detail})"
        match_summary = (
            f"{len(j.matches)} (exact: {sum(1 for m in j.matches if m.similarity == 'exact')})"
            if j.matches
            else "-"
        )
        table.add_row(j.jurisdiction.upper(), status_text, match_summary, j.deeplink or "-")
    return table


def _typosquat_table(typo: TyposquatReport) -> Table:
    table = Table(title=f"Typosquat / brand similarity for '{typo.sld}'", show_header=True, header_style="bold")
    table.add_column("Brand")
    table.add_column("Distance", justify="right")
    table.add_column("Kind")
    if not typo.matches:
        table.add_row("(no matches)", "-", "-")
    for m in typo.matches[:10]:
        table.add_row(m.brand, str(m.distance), m.kind)
    return table


def _handles_table(handles: HandleReport) -> Table:
    table = Table(title=f"Handle availability for '{handles.sld}'", show_header=True, header_style="bold")
    table.add_column("Platform")
    table.add_column("Status")
    table.add_column("Detail")
    for r in handles.results:
        style = _HANDLE_STATUS_STYLES.get(r.status, "")
        table.add_row(r.platform, f"[{style}]{r.status}[/]" if style else r.status, r.detail or "-")
    return table


def _history_table(history: HistoryReport) -> Table:
    table = Table(title="History (Wayback Machine)", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("has archive", "yes" if history.has_archive else "no")
    table.add_row("snapshot count", str(history.snapshot_count))
    table.add_row("first seen", history.first_seen or "-")
    table.add_row("last seen", history.last_seen or "-")
    table.add_row("archive span (days)", str(history.age_days) if history.age_days is not None else "-")
    return table


def _render_verdict(
    domain: str,
    basic: BasicReport,
    history: HistoryReport | None,
    handles: HandleReport | None,
    typo: TyposquatReport | None,
    trademark: TrademarkReport | None,
    semantics: SemanticsReport | None,
    llmo: LlmoReport | None,
    homograph: HomographReport | None,
    verdict: Verdict,
) -> None:
    console.print(
        f"\n[bold]{domain}[/bold]  →  "
        f"[{_BAND_STYLES[verdict.band]}]{verdict.band.value}[/]  "
        f"score=[bold]{verdict.score}[/]/100  — {verdict.summary}\n"
    )
    console.print(_basic_table(basic))
    _emit_lines("Issues", basic.issues, style="bold red")
    _emit_lines("Notes", basic.notes, style="bold")

    if history is not None:
        console.print(_history_table(history))
        _emit_lines("History issues", history.issues, style="bold red")
        _emit_lines("History notes", history.notes, style="bold")

    if handles is not None:
        console.print(_handles_table(handles))
        _emit_lines("Handle notes", handles.notes, style="bold")

    if typo is not None:
        console.print(_typosquat_table(typo))
        _emit_lines("Typosquat issues", typo.issues, style="bold red")
        _emit_lines("Typosquat notes", typo.notes, style="bold")

    if trademark is not None:
        console.print(_trademark_table(trademark))
        _emit_lines("Trademark issues", trademark.issues, style="bold red")
        _emit_lines("Trademark notes", trademark.notes, style="bold")

    if semantics is not None:
        console.print(_semantics_table(semantics))
        _emit_lines("Semantics issues", semantics.issues, style="bold red")
        _emit_lines("Semantics notes", semantics.notes, style="bold")

    if llmo is not None:
        console.print(_llmo_table(llmo))
        _emit_lines("LLMO issues", llmo.issues, style="bold red")
        _emit_lines("LLMO notes", llmo.notes, style="bold")

    if homograph is not None and (homograph.is_idn or homograph.severity != "clean"):
        console.print(_homograph_table(homograph))
        _emit_lines("Homograph issues", homograph.issues, style="bold red")
        _emit_lines("Homograph notes", homograph.notes, style="bold")

    if verdict.deductions:
        dt = Table(title="Score deductions", show_header=True, header_style="bold")
        dt.add_column("Reason")
        dt.add_column("Points", justify="right")
        for reason, points in verdict.deductions:
            dt.add_row(reason, f"-{points}")
        console.print(dt)


def _payload(
    domain: str,
    basic: BasicReport,
    history: HistoryReport | None,
    handles: HandleReport | None,
    typo: TyposquatReport | None,
    trademark: TrademarkReport | None,
    semantics: SemanticsReport | None,
    llmo: LlmoReport | None,
    homograph: HomographReport | None,
    verdict: Verdict | None,
) -> dict[str, Any]:
    return {
        "domain": domain,
        "verdict": (
            None
            if verdict is None
            else {
                "score": verdict.score,
                "band": verdict.band.value,
                "summary": verdict.summary,
                "deductions": [{"reason": r, "points": p} for r, p in verdict.deductions],
            }
        ),
        "basic": {**asdict(basic), "length": basic.length},
        "history": None if history is None else asdict(history),
        "handles": None if handles is None else asdict(handles),
        "typosquat": None if typo is None else asdict(typo),
        "trademark": None if trademark is None else asdict(trademark),
        "semantics": None if semantics is None else asdict(semantics),
        "llmo": None if llmo is None else asdict(llmo),
        "homograph": None if homograph is None else asdict(homograph),
    }


def _emit_json(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_single(section: str, report: Any, as_json: bool) -> bool:
    """Emit JSON for a single-section subcommand; return True if JSON was emitted."""
    if as_json:
        _emit_json({"domain": report.domain, section: asdict(report)})
        return True
    return False


def _split_csv(s: str | None) -> list[str] | None:
    if not s:
        return None
    parts = [x.strip() for x in s.split(",") if x.strip()]
    return parts or None


@click.group(invoke_without_command=True)
@click.version_option(package_name="domain-pre-flight")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Pre-flight checks before registering a domain."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("domain")
@click.option("--no-history", is_flag=True, default=False, help="Skip Wayback Machine history lookup.")
@click.option(
    "--check-handles",
    "check_handles_flag",
    is_flag=True,
    default=False,
    help="Also check same-name availability on GitHub / npm / PyPI / X / Instagram.",
)
@click.option(
    "--no-typosquat",
    is_flag=True,
    default=False,
    help="Skip typosquat / brand-similarity check.",
)
@click.option(
    "--check-trademark",
    "check_trademark_flag",
    is_flag=True,
    default=False,
    help="Also query USPTO / EUIPO trademark registries (slow; J-PlatPat surfaced as deeplink only).",
)
@click.option(
    "--trademark-jurisdictions",
    default="us,eu,jp",
    help="Comma-separated jurisdictions for --check-trademark (default: us,eu,jp).",
)
@click.option(
    "--no-semantics",
    is_flag=True,
    default=False,
    help="Skip multi-language negative-meaning scan.",
)
@click.option(
    "--languages",
    default=",".join(SUPPORTED_LANGUAGES),
    help=f"Comma-separated language codes for the semantics scan (default: {','.join(SUPPORTED_LANGUAGES)}).",
)
@click.option(
    "--no-llmo",
    is_flag=True,
    default=False,
    help="Skip pronunciation / memorability (LLMO fitness) heuristic.",
)
@click.option(
    "--no-homograph",
    is_flag=True,
    default=False,
    help="Skip IDN homograph attack detection.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON instead of a rich table.")
def check(
    domain: str,
    no_history: bool,
    check_handles_flag: bool,
    no_typosquat: bool,
    check_trademark_flag: bool,
    trademark_jurisdictions: str,
    no_semantics: bool,
    languages: str,
    no_llmo: bool,
    no_homograph: bool,
    as_json: bool,
) -> None:
    """Run all enabled checks on DOMAIN and emit a verdict."""
    basic = check_basic(domain)
    history = None if no_history else check_history(domain)
    handles = check_handles(domain) if check_handles_flag else None
    typo = None if no_typosquat else check_typosquat(domain)
    trademark = (
        check_trademark(domain, jurisdictions=_split_csv(trademark_jurisdictions))
        if check_trademark_flag
        else None
    )
    semantics = (
        None
        if no_semantics
        else check_semantics(domain, languages=_split_csv(languages))
    )
    llmo = None if no_llmo else check_llmo(domain)
    homograph = None if no_homograph else check_idn_homograph(domain)
    verdict = aggregate(basic, history, typo, trademark, semantics, llmo, homograph)

    if as_json:
        _emit_json(_payload(domain, basic, history, handles, typo, trademark, semantics, llmo, homograph, verdict))
    else:
        _render_verdict(domain, basic, history, handles, typo, trademark, semantics, llmo, homograph, verdict)

    sys.exit(EXIT_CODES[verdict.band])


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def history(domain: str, as_json: bool) -> None:
    """Show only the Wayback Machine history for DOMAIN."""
    h = check_history(domain)
    if _emit_single("history", h, as_json):
        return

    console.print(f"\n[bold]{h.domain}[/]  archived={h.has_archive}  snapshots={h.snapshot_count}")
    console.print(f"first_seen={h.first_seen}  last_seen={h.last_seen}  span_days={h.age_days}")
    _emit_lines("Notes", h.notes)
    _emit_lines("Issues", h.issues, style="bold red")


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def homograph(domain: str, as_json: bool) -> None:
    """Detect whether the SLD visually mimics a known Latin brand (UTS #39)."""
    report = check_idn_homograph(domain)
    if _emit_single("homograph", report, as_json):
        return

    console.print(_homograph_table(report))
    _emit_lines("Issues", report.issues, style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def llmo(domain: str, as_json: bool) -> None:
    """Show only the LLMO fitness (pronunciation / memorability) for DOMAIN."""
    report = check_llmo(domain)
    if _emit_single("llmo", report, as_json):
        return

    console.print(_llmo_table(report))
    _emit_lines("Issues", report.issues, style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option(
    "--languages",
    default=",".join(SUPPORTED_LANGUAGES),
    help=f"Comma-separated language codes (default: {','.join(SUPPORTED_LANGUAGES)}).",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def semantics(domain: str, languages: str, as_json: bool) -> None:
    """Scan the SLD for negative-meaning terms across major languages."""
    report = check_semantics(domain, languages=_split_csv(languages))
    if _emit_single("semantics", report, as_json):
        return

    console.print(_semantics_table(report))
    _emit_lines("Issues", report.issues, style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option("--jurisdictions", default="us,eu,jp", help="Comma-separated jurisdictions (default: us,eu,jp).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def trademark(domain: str, jurisdictions: str, as_json: bool) -> None:
    """Query trademark registries for marks similar to the SLD."""
    report = check_trademark(domain, jurisdictions=_split_csv(jurisdictions))
    if _emit_single("trademark", report, as_json):
        return

    console.print(_trademark_table(report))
    _emit_lines("Issues", report.issues, style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def typosquat(domain: str, as_json: bool) -> None:
    """Show only the typosquat / brand-similarity check for DOMAIN."""
    report = check_typosquat(domain)
    if _emit_single("typosquat", report, as_json):
        return

    console.print(_typosquat_table(report))
    _emit_lines("Issues", report.issues, style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option(
    "--platforms",
    default=None,
    help="Comma-separated subset of platforms (default: github,npm,pypi,twitter,instagram).",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def handles(domain: str, platforms: str | None, as_json: bool) -> None:
    """Check same-name handle availability across developer platforms and social networks."""
    report = check_handles(domain, platforms=_split_csv(platforms))
    if _emit_single("handles", report, as_json):
        return

    console.print(_handles_table(report))
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def basic(domain: str, as_json: bool) -> None:
    """Run only offline structural checks on DOMAIN."""
    b = check_basic(domain)
    if as_json:
        _emit_json({"domain": b.domain, "basic": {**asdict(b), "length": b.length}})
        return

    console.print(_basic_table(b))
    _emit_lines("Issues", b.issues, style="bold red")
    _emit_lines("Notes", b.notes, style="bold")


if __name__ == "__main__":
    main()
