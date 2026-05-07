"""Pronunciation / memorability heuristic (LLMO fitness).

This is the most subjective check in the suite. It gives a 0-20 fitness
score across four axes, deliberately heuristic and English-leaning. Treat
the output as a discussion prompt, not a verdict.

Axes (each 0-5):

- ``cluster``  — penalise long consecutive consonant runs (hard to dictate)
- ``vowel``    — penalise vowel ratios far from the 0.30-0.55 sweet spot
- ``length``   — reward 4-12 char SLDs (memorable), penalise extremes
- ``repeats``  — penalise long runs of the same character (`ggg`, `aaa`)

Bands:
- 16-20  excellent  — easy to dictate, easy to remember
- 11-15  good       — usable, minor friction
- 6-10   ok         — noticeable friction
- 0-5    poor       — significant friction; reconsider
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VOWELS = set("aeiouy")

LlmoBand = Literal["excellent", "good", "ok", "poor"]


@dataclass
class LlmoReport:
    domain: str
    sld: str
    cluster_score: int = 0
    vowel_score: int = 0
    length_score: int = 0
    repeats_score: int = 0
    fitness: int = 0
    band: LlmoBand = "poor"
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _max_consecutive_consonants(name: str) -> int:
    longest = 0
    current = 0
    for ch in name:
        if ch.isalpha() and ch not in VOWELS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _max_repeat_run(name: str) -> int:
    longest = 0
    current = 1
    for i in range(1, len(name)):
        if name[i] == name[i - 1]:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return max(longest, 1 if name else 0)


def _vowel_ratio(name: str) -> float:
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in VOWELS) / len(letters)


def _band_for(score: int) -> LlmoBand:
    if score >= 16:
        return "excellent"
    if score >= 11:
        return "good"
    if score >= 6:
        return "ok"
    return "poor"


def check_llmo(domain: str) -> LlmoReport:
    """Score the SLD's voice/AI-friendliness on a 0-20 scale."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = LlmoReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — LLMO fitness skipped")
        return report

    cluster = _max_consecutive_consonants(sld)
    if cluster <= 2:
        report.cluster_score = 5
    elif cluster == 3:
        report.cluster_score = 3
    elif cluster == 4:
        report.cluster_score = 1
    else:
        report.cluster_score = 0

    if cluster >= 4:
        report.notes.append(f"consonant cluster of {cluster} — voice-spell friction")

    vr = _vowel_ratio(sld)
    if 0.30 <= vr <= 0.55:
        report.vowel_score = 5
    elif 0.20 <= vr <= 0.65:
        report.vowel_score = 3
    elif 0.10 <= vr <= 0.75:
        report.vowel_score = 1
    else:
        report.vowel_score = 0

    if vr < 0.20:
        report.notes.append(f"low vowel ratio ({vr:.2f}) — likely hard to pronounce")
    elif vr > 0.65:
        report.notes.append(f"vowel-heavy ({vr:.2f}) — may sound generic")

    n = len(sld)
    if 4 <= n <= 9:
        report.length_score = 5
    elif n == 3 or 10 <= n <= 12:
        report.length_score = 3
    elif n == 2 or 13 <= n <= 15:
        report.length_score = 1
    else:
        report.length_score = 0

    if n > 12:
        report.notes.append(f"length {n} — harder to memorise")
    elif n < 3:
        report.notes.append(f"length {n} — premium / generic feel")

    repeat = _max_repeat_run(sld)
    if repeat <= 1:
        report.repeats_score = 5
    elif repeat == 2:
        report.repeats_score = 4
    elif repeat == 3:
        report.repeats_score = 2
    else:
        report.repeats_score = 0

    if repeat >= 3:
        report.notes.append(f"repeated character run of length {repeat}")

    report.fitness = (
        report.cluster_score
        + report.vowel_score
        + report.length_score
        + report.repeats_score
    )
    report.band = _band_for(report.fitness)

    if report.band == "poor":
        report.issues.append(
            f"LLMO fitness {report.fitness}/20 — significant voice/memorability friction"
        )

    return report
