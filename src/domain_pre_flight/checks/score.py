"""Aggregate scoring across check modules.

Score is a 0-100 number; verdict bands:
  90-100 GREEN  — go ahead
  70-89  YELLOW — usable, watch the listed concerns
  40-69  ORANGE — acceptable only with mitigation
   0-39  RED    — do not register without manual review
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .basic import BasicReport
from .history import HistoryReport


@dataclass
class Verdict:
    score: int
    band: str  # GREEN / YELLOW / ORANGE / RED
    summary: str
    deductions: list[tuple[str, int]] = field(default_factory=list)


def _band(score: int) -> str:
    if score >= 90:
        return "GREEN"
    if score >= 70:
        return "YELLOW"
    if score >= 40:
        return "ORANGE"
    return "RED"


def score_basic(report: BasicReport) -> tuple[int, list[tuple[str, int]]]:
    """Return (deduction_total, [(reason, points), ...]) for basic checks."""
    deductions: list[tuple[str, int]] = []

    if not report.is_valid_syntax:
        deductions.append(("invalid hostname syntax", 100))
        return 100, deductions

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

    deductions.append((f".{report.tld} TLD risk", report.tld_risk_score))

    total = sum(d for _, d in deductions)
    return total, deductions


def score_history(report: HistoryReport) -> tuple[int, list[tuple[str, int]]]:
    """Return (deduction_total, deductions). Only deducts for high-risk patterns;
    a clean history with snapshots is *not* penalised here.
    """
    deductions: list[tuple[str, int]] = []
    if report.snapshot_count >= 1000:
        deductions.append(
            ("very large prior snapshot count — manual content audit required", 25)
        )
    elif report.snapshot_count >= 100:
        deductions.append(("substantial prior content — audit before adopting topic", 10))
    return sum(d for _, d in deductions), deductions


def aggregate(basic: BasicReport, history: HistoryReport | None = None) -> Verdict:
    """Combine sub-reports into a single verdict."""
    deductions: list[tuple[str, int]] = []

    basic_deduction, basic_items = score_basic(basic)
    deductions.extend(basic_items)

    if history is not None:
        _, history_items = score_history(history)
        deductions.extend(history_items)

    total_deduction = min(100, sum(d for _, d in deductions))
    score = max(0, 100 - total_deduction)
    band = _band(score)

    if band == "GREEN":
        summary = "Looks clean. Proceed."
    elif band == "YELLOW":
        summary = "Usable; review the listed concerns."
    elif band == "ORANGE":
        summary = "Acceptable only with mitigation. Investigate flagged items."
    else:
        summary = "Do not register without manual review."

    return Verdict(score=score, band=band, summary=summary, deductions=deductions)
