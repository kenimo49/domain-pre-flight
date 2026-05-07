"""Typosquat / brand-similarity detection.

Compares the candidate SLD against a curated list of well-known brand stems
using Levenshtein edit distance plus a couple of squatting-pattern heuristics
(homoglyph substitution, bigram-set match with different ordering).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files

import Levenshtein

# Common visual / phonetic substitutions used by typosquatters.
HOMOGLYPHS = {
    "0": "o", "1": "l", "5": "s", "$": "s", "@": "a",
    "rn": "m", "vv": "w",
}

# Distance tiers (from candidate SLD to a brand stem).
EXACT_MATCH = 0
NEAR_DISTANCE = 2  # 1 or 2 = high-risk
POSSIBLE_DISTANCE = 3  # exactly 3 = note only


@dataclass
class BrandMatch:
    brand: str
    distance: int
    kind: str  # "exact" | "near" | "possible" | "homoglyph" | "bigram"


@dataclass
class TyposquatReport:
    domain: str
    sld: str
    matches: list[BrandMatch] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def worst_kind(self) -> str | None:
        order = {"exact": 0, "near": 1, "homoglyph": 1, "bigram": 2, "possible": 3}
        if not self.matches:
            return None
        return min((m.kind for m in self.matches), key=lambda k: order.get(k, 99))


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


def check_typosquat(domain: str, brands: list[str] | None = None) -> TyposquatReport:
    """Return matches between the candidate SLD and known brand stems."""
    from .basic import parse_domain

    domain = domain.strip().lower().rstrip(".")
    sld, _ = parse_domain(domain)
    report = TyposquatReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — typosquat check skipped")
        return report

    brand_list = brands if brands is not None else load_brands()
    sld_homoglyph = _normalise_homoglyphs(sld)
    sld_bigrams = _bigrams(sld)

    # Near/homoglyph/bigram matching is meaningless for very short SLDs:
    # distance 2 against a 2-char brand is "totally different word."
    similarity_eligible = len(sld) >= 4

    seen: set[str] = set()
    for brand in brand_list:
        if brand in seen:
            continue
        seen.add(brand)

        if sld == brand:
            report.matches.append(BrandMatch(brand, 0, "exact"))
            continue

        if not similarity_eligible or len(brand) < 4:
            continue

        # Homoglyph wins over plain Levenshtein when the de-substituted form
        # matches the brand more closely — that pattern is the actual signal
        # of a typosquat ("g00gle" -> "google" with distance 0 after
        # normalisation).
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

    # Build human-readable issues / notes.
    severe = [m for m in report.matches if m.kind in {"exact", "near", "homoglyph", "bigram"}]
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
