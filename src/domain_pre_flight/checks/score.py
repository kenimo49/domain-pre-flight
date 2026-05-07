"""Aggregate scoring across check modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .basic import BasicReport, tld_risk_for
from .history import HistoryReport
from .llmo import LlmoReport
from .semantics import SemanticsReport
from .trademark import TrademarkReport
from .typosquat import TyposquatReport


class Band(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


_BAND_THRESHOLDS: list[tuple[int, Band]] = [
    (90, Band.GREEN),
    (70, Band.YELLOW),
    (40, Band.ORANGE),
    (0, Band.RED),
]

_SUMMARIES: dict[Band, str] = {
    Band.GREEN: "Looks clean. Proceed.",
    Band.YELLOW: "Usable; review the listed concerns.",
    Band.ORANGE: "Acceptable only with mitigation. Investigate flagged items.",
    Band.RED: "Do not register without manual review.",
}

EXIT_CODES: dict[Band, int] = {
    Band.GREEN: 0,
    Band.YELLOW: 0,
    Band.ORANGE: 1,
    Band.RED: 2,
}


@dataclass
class Verdict:
    score: int
    band: Band
    summary: str
    deductions: list[tuple[str, int]] = field(default_factory=list)


def _band_for(score: int) -> Band:
    for threshold, band in _BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return Band.RED


def _basic_deductions(report: BasicReport) -> list[tuple[str, int]]:
    if not report.is_valid_syntax:
        return [("invalid hostname syntax", 100)]

    deductions: list[tuple[str, int]] = []

    if report.label_length < 3:
        deductions.append(("SLD <3 chars (premium/reserved)", 15))
    elif report.label_length > 20:
        deductions.append(("SLD >20 chars (memory-unfriendly)", 15))
    elif report.label_length > 15:
        deductions.append(("SLD >15 chars", 5))

    if report.hyphens >= 2:
        deductions.append((f"{report.hyphens} hyphens in SLD", 20))
    elif report.hyphens == 1:
        deductions.append(("1 hyphen in SLD", 5))

    if report.digits >= 2:
        deductions.append((f"{report.digits} digits in SLD", 15))
    elif report.digits == 1:
        deductions.append(("1 digit in SLD", 5))

    if report.has_idn:
        deductions.append(("IDN / punycode (phishing perception)", 10))

    deductions.append((f".{report.tld} TLD risk", tld_risk_for(report.tld)))
    return deductions


def _history_deductions(report: HistoryReport) -> list[tuple[str, int]]:
    if report.snapshot_count >= 1000:
        return [("very large prior snapshot count — manual content audit required", 25)]
    if report.snapshot_count >= 100:
        return [("substantial prior content — audit before adopting topic", 10)]
    return []


def _typosquat_deductions(report: TyposquatReport) -> list[tuple[str, int]]:
    if not report.matches:
        return []
    severe = [m for m in report.matches if m.kind in {"exact", "near", "homoglyph", "bigram"}]
    if not severe:
        return []
    first = severe[0]
    if first.kind == "exact":
        return [(f"identical to known brand '{first.brand}'", 60)]
    if first.kind in {"near", "homoglyph"}:
        return [(f"resembles known brand '{first.brand}' ({first.kind})", 30)]
    return [(f"shares bigram set with '{first.brand}'", 15)]


def _trademark_deductions(report: TrademarkReport) -> list[tuple[str, int]]:
    # The trademark module is deeplink-only as of ADR 0009; no machine-
    # detected matches exist, so there is nothing to deduct. Kept as a
    # function (returning []) so a future live-query restoration can plug
    # weights back in without touching aggregate(...).
    return []


def _semantics_deductions(report: SemanticsReport) -> list[tuple[str, int]]:
    if not report.matches:
        return []
    severe_exact = [m for m in report.matches if m.severity == "severe" and m.kind == "exact"]
    severe_substring = [m for m in report.matches if m.severity == "severe" and m.kind == "substring"]
    if severe_exact:
        m = severe_exact[0]
        return [(f"identical to severe negative term '{m.term}' ({m.language})", 70)]
    if severe_substring:
        m = severe_substring[0]
        return [(f"contains severe negative term '{m.term}' ({m.language})", 30)]
    return []


def _llmo_deductions(report: LlmoReport) -> list[tuple[str, int]]:
    if report.fitness == 0 and not report.sld:
        return []
    if report.band == "poor":
        return [(f"LLMO fitness {report.fitness}/20 (poor — voice/memorability friction)", 10)]
    if report.band == "ok":
        return [(f"LLMO fitness {report.fitness}/20 (ok — minor friction)", 3)]
    return []


def aggregate(
    basic: BasicReport,
    history: HistoryReport | None = None,
    typosquat: TyposquatReport | None = None,
    trademark: TrademarkReport | None = None,
    semantics: SemanticsReport | None = None,
    llmo: LlmoReport | None = None,
) -> Verdict:
    deductions = _basic_deductions(basic)
    if history is not None:
        deductions.extend(_history_deductions(history))
    if typosquat is not None:
        deductions.extend(_typosquat_deductions(typosquat))
    if trademark is not None:
        deductions.extend(_trademark_deductions(trademark))
    if semantics is not None:
        deductions.extend(_semantics_deductions(semantics))
    if llmo is not None:
        deductions.extend(_llmo_deductions(llmo))

    total = min(100, sum(points for _, points in deductions))
    score = max(0, 100 - total)
    band = _band_for(score)
    return Verdict(score=score, band=band, summary=_SUMMARIES[band], deductions=deductions)
