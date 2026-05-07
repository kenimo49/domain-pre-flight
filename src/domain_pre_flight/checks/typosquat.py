"""Typosquat / brand-similarity detection.

Compares the candidate SLD against a curated list of well-known brand stems
using Levenshtein edit distance plus a couple of squatting-pattern heuristics
(homoglyph substitution, bigram-set match with different ordering).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from typing import Literal

import Levenshtein

HOMOGLYPHS = {
    "0": "o", "1": "l", "5": "s", "$": "s", "@": "a",
    "rn": "m", "vv": "w",
}

EXACT_MATCH = 0
NEAR_DISTANCE = 2
POSSIBLE_DISTANCE = 3

MatchKind = Literal["exact", "near", "homoglyph", "bigram", "possible"]

# Single source of truth: most-severe first. _worst_kind picks the lowest index.
_KIND_ORDER: tuple[MatchKind, ...] = ("exact", "near", "homoglyph", "bigram", "possible")
_SEVERE_KINDS = frozenset({"exact", "near", "homoglyph", "bigram"})


@dataclass
class BrandMatch:
    brand: str
    distance: int
    kind: MatchKind


@dataclass
class TyposquatReport:
    domain: str
    sld: str
    matches: list[BrandMatch] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def worst_kind(self) -> MatchKind | None:
        if not self.matches:
            return None
        return min(
            (m.kind for m in self.matches),
            key=lambda k: _KIND_ORDER.index(k) if k in _KIND_ORDER else len(_KIND_ORDER),
        )


def _normalise_homoglyphs(name: str) -> str:
    out = name.lower()
    for src, dst in HOMOGLYPHS.items():
        out = out.replace(src, dst)
    return out


def _bigrams(name: str) -> set[str]:
    return {name[i : i + 2] for i in range(len(name) - 1)} if len(name) >= 2 else set()


def load_brands() -> list[str]:
    """Read the bundled brand list, ignoring blank lines and ``#`` comments."""
    path = files("domain_pre_flight.data") / "known_brands.txt"
    text = path.read_text(encoding="utf-8")
    return [
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def check_typosquat(domain: str, *, brands: list[str] | None = None) -> TyposquatReport:
    """Return matches between the candidate SLD and known brand stems."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = TyposquatReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — typosquat check skipped")
        return report

    brand_list = brands if brands is not None else load_brands()
    sld_homoglyph = _normalise_homoglyphs(sld)
    sld_bigrams = _bigrams(sld)

    # Distance 2 against a 2-char brand is "totally different word"; exempt
    # short SLDs and short brands from similarity matching.
    similarity_eligible = len(sld) >= 4

    for brand in brand_list:
        if sld == brand:
            report.matches.append(BrandMatch(brand, 0, "exact"))
            continue

        if not similarity_eligible or len(brand) < 4:
            continue

        # Homoglyph wins over plain Levenshtein: "g00gle" -> "google" at
        # distance 0 after normalisation is the actual typosquat signal.
        if sld_homoglyph != sld:
            hg_distance = Levenshtein.distance(sld_homoglyph, brand)
            if hg_distance <= 1:
                report.matches.append(BrandMatch(brand, hg_distance, "homoglyph"))
                continue

        distance = Levenshtein.distance(sld, brand)

        if distance <= NEAR_DISTANCE:
            report.matches.append(BrandMatch(brand, distance, "near"))
            continue

        if distance == POSSIBLE_DISTANCE:
            report.matches.append(BrandMatch(brand, distance, "possible"))
            continue

        if abs(len(sld) - len(brand)) <= 1:
            brand_bigrams = _bigrams(brand)
            if sld_bigrams and brand_bigrams and sld_bigrams == brand_bigrams:
                report.matches.append(BrandMatch(brand, distance, "bigram"))

    severe = [m for m in report.matches if m.kind in _SEVERE_KINDS]
    notes_only = [m for m in report.matches if m.kind == "possible"]

    if severe:
        first = severe[0]
        if first.kind == "exact":
            report.issues.append(f"SLD is identical to known brand '{first.brand}' — UDRP / trademark risk")
        else:
            report.issues.append(
                f"SLD resembles known brand '{first.brand}' (distance {first.distance}, {first.kind}) — UDRP risk"
            )
        if len(severe) > 1:
            report.issues.append(
                f"also resembles: {', '.join(m.brand for m in severe[1:5])}"
            )

    for m in notes_only[:5]:
        report.notes.append(f"loosely resembles '{m.brand}' (distance {m.distance})")

    return report
