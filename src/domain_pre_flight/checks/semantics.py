"""Multi-language negative-meaning scan for the candidate SLD.

Bundled per-language word lists live at
``src/domain_pre_flight/data/negative_meanings/<lang>.txt``. Each line is a
``term`` plus an optional tab-separated ``severity`` (``severe`` or
``mild``). Empty lines and ``#`` comments are skipped.

Match modes:

- ``exact``     — the SLD equals the term
- ``substring`` — the SLD contains the term as a substring (≥4-char terms only,
                  to avoid trigger-happy false positives)

This check is curated rather than crowd-sourced; pull requests adding terms
must include a citation. Substring matches are biased toward ``note``
rather than ``issue`` for ``mild`` severity to keep noise low.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from typing import Literal

Severity = Literal["severe", "mild"]
SUPPORTED_LANGUAGES = ["en", "es", "pt", "ja", "ko", "zh"]


@dataclass
class SemanticMatch:
    language: str
    term: str
    severity: Severity
    kind: Literal["exact", "substring"]


@dataclass
class SemanticsReport:
    domain: str
    sld: str
    languages: list[str] = field(default_factory=list)
    matches: list[SemanticMatch] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _load_language(lang: str) -> list[tuple[str, Severity]]:
    path = files("domain_pre_flight.data.negative_meanings") / f"{lang}.txt"
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return []

    entries: list[tuple[str, Severity]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        term = parts[0].strip().lower()
        severity: Severity = "mild"
        if len(parts) > 1 and parts[1].strip() == "severe":
            severity = "severe"
        if term:
            entries.append((term, severity))
    return entries


def check_semantics(
    domain: str,
    *,
    languages: list[str] | None = None,
) -> SemanticsReport:
    """Scan the SLD for negative-meaning terms in the requested languages."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    selected = languages if languages else list(SUPPORTED_LANGUAGES)
    report = SemanticsReport(domain=domain, sld=sld, languages=selected)

    if not sld:
        report.notes.append("no SLD parsed — semantics check skipped")
        return report

    unknown = [l for l in selected if l not in SUPPORTED_LANGUAGES]
    if unknown:
        report.notes.append(f"ignored unsupported languages: {', '.join(unknown)}")
    selected = [l for l in selected if l in SUPPORTED_LANGUAGES]

    for lang in selected:
        for term, severity in _load_language(lang):
            if sld == term:
                report.matches.append(SemanticMatch(lang, term, severity, "exact"))
            elif len(term) >= 4 and term in sld:
                report.matches.append(SemanticMatch(lang, term, severity, "substring"))

    severe_exact = [m for m in report.matches if m.severity == "severe" and m.kind == "exact"]
    severe_substring = [m for m in report.matches if m.severity == "severe" and m.kind == "substring"]
    mild = [m for m in report.matches if m.severity == "mild"]

    if severe_exact:
        sample = severe_exact[0]
        report.issues.append(
            f"SLD is identical to a severe term ('{sample.term}', {sample.language}) — do not register"
        )
    elif severe_substring:
        sample = severe_substring[0]
        report.issues.append(
            f"SLD contains severe term '{sample.term}' ({sample.language}) — likely problematic"
        )

    for m in mild[:5]:
        report.notes.append(
            f"contains mild negative term '{m.term}' ({m.language}, {m.kind})"
        )

    return report
