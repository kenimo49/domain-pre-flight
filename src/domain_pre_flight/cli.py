"""Command-line interface for domain-pre-flight."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .checks.basic import BasicReport, check_basic
from .checks.dns_sanity import DnsSanityReport, check_dns_sanity
from .checks.handles import HandleReport, check_handles
from .checks.history import HistoryReport, check_history
from .checks.idn_homograph import HomographReport, check_idn_homograph
from .checks.llmo import LlmoReport, check_llmo
from .checks.permutations import generate_permutations
from .checks.rdap import RdapReport, check_rdap
from .checks.score import EXIT_CODES, Band, Verdict, aggregate
from .checks.semantics import SUPPORTED_LANGUAGES, SemanticsReport, check_semantics
from .checks.trademark import TrademarkReport, check_trademark
from .checks.suggest import SuggestReport, check_suggest
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


def _dns_sanity_table(r: DnsSanityReport) -> Table:
    table = Table(title=f"DNS hygiene for '{r.domain}'", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("MX", r.mx)
    table.add_row("SPF", r.spf)
    table.add_row("DMARC", r.dmarc)
    table.add_row("DKIM", r.dkim)
    if r.mx_records:
        table.add_row("MX hosts", ", ".join(r.mx_records[:3]))
    return table


def _rdap_table(r: RdapReport) -> Table:
    table = Table(title=f"RDAP for '{r.domain}'", show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("status", f"{r.status}{f' ({r.detail})' if r.detail else ''}")
    table.add_row("created", r.created_at or "-")
    table.add_row("expires", r.expires_at or "-")
    table.add_row("age (days)", str(r.domain_age_days) if r.domain_age_days is not None else "-")
    table.add_row("days to expiry", str(r.days_to_expiry) if r.days_to_expiry is not None else "-")
    table.add_row("registrar", r.registrar or "-")
    table.add_row("registry status", ", ".join(r.domain_status) or "-")
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


def _suggest_table(report: SuggestReport) -> Table:
    table = Table(
        title=f"📡 Related domain suggestions for '{report.source_sld}'",
        show_header=True,
        header_style="bold",
    )
    table.add_column("domain")
    table.add_column(".com", justify="center")
    table.add_column("HN 30d", justify="right")
    table.add_column("signal", justify="center")
    for c in report.candidates:
        if c.available is True:
            avail = "[bold green]✅ free[/]"
            mentions = str(c.hn_mentions_30d)
            sig = c.signal
        elif c.available is False:
            avail = "[dim]❌ taken[/]"
            mentions = "-"
            sig = ""
        else:
            avail = "[yellow]? unknown[/]"
            mentions = "-"
            sig = ""
        table.add_row(c.domain, avail, mentions, sig)
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


@dataclass
class CheckResults:
    """Per-section reports produced by the aggregate `check` subcommand."""

    basic: BasicReport
    history: HistoryReport | None = None
    handles: HandleReport | None = None
    typosquat: TyposquatReport | None = None
    trademark: TrademarkReport | None = None
    semantics: SemanticsReport | None = None
    llmo: LlmoReport | None = None
    homograph: HomographReport | None = None
    rdap: RdapReport | None = None
    dns_sanity: DnsSanityReport | None = None


# (attribute on CheckResults, label prefix for issues/notes, table renderer,
#  optional predicate deciding whether a present report is worth showing)
_SECTIONS: tuple[tuple[str, str, Callable[[Any], Table], Callable[[Any], bool] | None], ...] = (
    ("history", "History", _history_table, None),
    ("handles", "Handle", _handles_table, None),
    ("typosquat", "Typosquat", _typosquat_table, None),
    ("trademark", "Trademark", _trademark_table, None),
    ("semantics", "Semantics", _semantics_table, None),
    ("llmo", "LLMO", _llmo_table, None),
    ("homograph", "Homograph", _homograph_table, lambda r: r.is_idn or r.severity != "clean"),
    ("rdap", "RDAP", _rdap_table, None),
    ("dns_sanity", "DNS", _dns_sanity_table, None),
)


def _render_verdict(domain: str, results: CheckResults, verdict: Verdict) -> None:
    console.print(
        f"\n[bold]{domain}[/bold]  →  "
        f"[{_BAND_STYLES[verdict.band]}]{verdict.band.value}[/]  "
        f"score=[bold]{verdict.score}[/]/100  — {verdict.summary}\n"
    )
    console.print(_basic_table(results.basic))
    _emit_lines("Issues", results.basic.issues, style="bold red")
    _emit_lines("Notes", results.basic.notes, style="bold")

    for attr, label, table_fn, predicate in _SECTIONS:
        report = getattr(results, attr)
        if report is None or (predicate is not None and not predicate(report)):
            continue
        console.print(table_fn(report))
        _emit_lines(f"{label} issues", getattr(report, "issues", []), style="bold red")
        _emit_lines(f"{label} notes", report.notes, style="bold")

    if verdict.deductions:
        dt = Table(title="Score deductions", show_header=True, header_style="bold")
        dt.add_column("Reason")
        dt.add_column("Points", justify="right")
        for reason, points in verdict.deductions:
            dt.add_row(reason, f"-{points}")
        console.print(dt)


def _payload(domain: str, results: CheckResults, verdict: Verdict | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        "basic": {**asdict(results.basic), "length": results.basic.length},
    }
    for attr, _label, _table_fn, _predicate in _SECTIONS:
        report = getattr(results, attr)
        payload[attr] = None if report is None else asdict(report)
    return payload


def _emit_json(payload: dict[str, Any]) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_single(section: str, report: Any, as_json: bool) -> bool:
    """Emit JSON for a single-section subcommand; return True if JSON was emitted."""
    if as_json:
        _emit_json({"domain": report.domain, section: asdict(report)})
        return True
    return False


def _emit_report(section: str, report: Any, table_fn: Callable[[Any], Table], as_json: bool) -> None:
    """Render a single-section subcommand: JSON, or table + issues + notes."""
    if _emit_single(section, report, as_json):
        return
    console.print(table_fn(report))
    _emit_lines("Issues", getattr(report, "issues", []), style="bold red")
    _emit_lines("Notes", report.notes, style="bold")


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
    "--llmo-locale",
    type=click.Choice(["en", "neutral"]),
    default="en",
    help="LLMO phonotactic locale (default: en).",
)
@click.option(
    "--no-homograph",
    is_flag=True,
    default=False,
    help="Skip IDN homograph attack detection.",
)
@click.option(
    "--check-rdap",
    "check_rdap_flag",
    is_flag=True,
    default=False,
    help="Also query RDAP for domain age, expiry, registrar, and registry status flags.",
)
@click.option(
    "--check-dns",
    "check_dns_flag",
    is_flag=True,
    default=False,
    help="Also probe MX / SPF / DMARC / DKIM presence (DNS lookups, ~5s).",
)
@click.option(
    "--suggest",
    "suggest_flag",
    is_flag=True,
    default=False,
    help=(
        "After the verdict, suggest related emerging-term .com domains with Hacker News trend signals. "
        "Requires ANTHROPIC_API_KEY and: pip install domain-pre-flight[suggest]"
    ),
)
@click.option(
    "--suggest-count",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Number of domain suggestions to generate (used with --suggest).",
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
    llmo_locale: str,
    no_homograph: bool,
    check_rdap_flag: bool,
    check_dns_flag: bool,
    suggest_flag: bool,
    suggest_count: int,
    as_json: bool,
) -> None:
    """Run all enabled checks on DOMAIN and emit a verdict."""
    results = CheckResults(
        basic=check_basic(domain),
        history=None if no_history else check_history(domain),
        handles=check_handles(domain) if check_handles_flag else None,
        typosquat=None if no_typosquat else check_typosquat(domain),
        trademark=(
            check_trademark(domain, jurisdictions=_split_csv(trademark_jurisdictions))
            if check_trademark_flag
            else None
        ),
        semantics=(
            None
            if no_semantics
            else check_semantics(domain, languages=_split_csv(languages))
        ),
        llmo=None if no_llmo else check_llmo(domain, locale=llmo_locale),  # type: ignore[arg-type]
        homograph=None if no_homograph else check_idn_homograph(domain),
        rdap=check_rdap(domain) if check_rdap_flag else None,
        dns_sanity=check_dns_sanity(domain) if check_dns_flag else None,
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

    if as_json:
        payload = _payload(domain, results, verdict)
        if suggest_flag:
            suggest = check_suggest(domain, count=suggest_count)
            from dataclasses import asdict as _asdict  # noqa: PLC0415
            payload["suggest"] = _asdict(suggest)
        _emit_json(payload)
    else:
        _render_verdict(domain, results, verdict)
        if suggest_flag:
            suggest = check_suggest(domain, count=suggest_count)
            console.print()
            if suggest.issues:
                _emit_lines("Suggest issues", suggest.issues, style="bold red")
            elif suggest.candidates:
                console.print(_suggest_table(suggest))
                _emit_lines("Suggest notes", suggest.notes, style="bold")

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
@click.option("--limit", type=int, default=None, help="Show only the first N permutations.")
@click.option("--kind", default=None, help="Filter by kind (omission/substitution/...).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def permutations(domain: str, limit: int | None, kind: str | None, as_json: bool) -> None:
    """Generate dnstwist-style typo / spoof permutations of the SLD."""
    report = generate_permutations(domain)
    if kind:
        report.permutations = [p for p in report.permutations if p.kind == kind]
    if limit:
        report.permutations = report.permutations[:limit]
    if as_json:
        _emit_json({"domain": report.base_domain, "permutations": asdict(report)})
        return
    table = Table(title=f"Permutations of '{report.sld}'", show_header=True, header_style="bold")
    table.add_column("Candidate")
    table.add_column("Kind")
    for p in report.permutations[:50]:
        table.add_row(p.candidate, p.kind)
    if len(report.permutations) > 50:
        table.add_row(f"... ({len(report.permutations) - 50} more)", "")
    console.print(table)
    _emit_lines("Notes", report.notes, style="bold")


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def dns(domain: str, as_json: bool) -> None:
    """Probe MX / SPF / DMARC / DKIM presence for DOMAIN."""
    _emit_report("dns_sanity", check_dns_sanity(domain), _dns_sanity_table, as_json)


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def rdap(domain: str, as_json: bool) -> None:
    """Query RDAP for domain age, expiry, registrar, and registry status."""
    _emit_report("rdap", check_rdap(domain), _rdap_table, as_json)


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def homograph(domain: str, as_json: bool) -> None:
    """Detect whether the SLD visually mimics a known Latin brand (UTS #39)."""
    _emit_report("homograph", check_idn_homograph(domain), _homograph_table, as_json)


@main.command()
@click.argument("domain")
@click.option(
    "--llmo-locale",
    type=click.Choice(["en", "neutral"]),
    default="en",
    help="Phonotactic locale (en: English bias, neutral: relaxes cluster penalty for transliterations).",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def llmo(domain: str, llmo_locale: str, as_json: bool) -> None:
    """Show only the LLMO fitness (pronunciation / memorability) for DOMAIN."""
    report = check_llmo(domain, locale=llmo_locale)  # type: ignore[arg-type]
    _emit_report("llmo", report, _llmo_table, as_json)


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
    _emit_report("semantics", report, _semantics_table, as_json)


@main.command()
@click.argument("domain")
@click.option("--jurisdictions", default="us,eu,jp", help="Comma-separated jurisdictions (default: us,eu,jp).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def trademark(domain: str, jurisdictions: str, as_json: bool) -> None:
    """Query trademark registries for marks similar to the SLD."""
    report = check_trademark(domain, jurisdictions=_split_csv(jurisdictions))
    _emit_report("trademark", report, _trademark_table, as_json)


@main.command()
@click.argument("domain")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON.")
def typosquat(domain: str, as_json: bool) -> None:
    """Show only the typosquat / brand-similarity check for DOMAIN."""
    _emit_report("typosquat", check_typosquat(domain), _typosquat_table, as_json)


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
    _emit_report("handles", report, _handles_table, as_json)


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
