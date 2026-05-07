"""dnstwist-style permutation generation for the candidate SLD.

For a candidate ``brand``, generate the set of plausible typo / spoof
variants that a phisher might register: omissions, substitutions,
transpositions, doublings, keyboard-adjacent substitutions, and
homoglyph substitutions. The output is the set of candidate *spoof*
domains the user might want to defensively register or monitor.

This module is **generation-only** — it does not perform availability
probes. Combining permutations with `check_handles` / `check_basic` /
WHOIS is left to the caller because the combinatorial cost grows
quickly. The CLI exposes a generate-only subcommand by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PermutationKind = Literal[
    "omission",
    "substitution",
    "transposition",
    "doubling",
    "keyboard_adjacent",
    "homoglyph",
    "addition",
    "hyphenation",
]

# US-QWERTY adjacency. Each key maps to its physical neighbours.
_KEYBOARD = {
    "q": "wa", "w": "qeas", "e": "wrsd", "r": "etdf", "t": "ryfg",
    "y": "tugh", "u": "yihj", "i": "uojk", "o": "ipkl", "p": "ol",
    "a": "qwsz", "s": "awedxz", "d": "serfcx", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "j": "huiknm", "k": "jiolm",
    "l": "kop", "z": "asx", "x": "zsdc", "c": "xdfv",
    "v": "cfgb", "b": "vghn", "n": "bhjm", "m": "njk",
}

# Visually similar character substitutions used by typosquatters.
_HOMOGLYPHS = {
    "o": "0",
    "0": "o",
    "l": "1",
    "1": "l",
    "i": "1",
    "s": "5",
    "5": "s",
    "e": "3",
    "3": "e",
    "a": "@",
}


@dataclass
class Permutation:
    candidate: str
    kind: PermutationKind


@dataclass
class PermutationReport:
    sld: str
    tld: str
    base_domain: str
    permutations: list[Permutation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _omissions(s: str) -> set[str]:
    return {s[:i] + s[i + 1 :] for i in range(len(s)) if len(s) > 1}


def _transpositions(s: str) -> set[str]:
    out: set[str] = set()
    for i in range(len(s) - 1):
        out.add(s[:i] + s[i + 1] + s[i] + s[i + 2 :])
    return out


def _doublings(s: str) -> set[str]:
    return {s[: i + 1] + s[i] + s[i + 1 :] for i in range(len(s))}


def _substitutions(s: str) -> set[str]:
    """Replace one character with each other letter a-z."""
    out: set[str] = set()
    for i, ch in enumerate(s):
        if not ch.isalpha():
            continue
        for c in "abcdefghijklmnopqrstuvwxyz":
            if c == ch:
                continue
            out.add(s[:i] + c + s[i + 1 :])
    return out


def _keyboard_adjacents(s: str) -> set[str]:
    out: set[str] = set()
    for i, ch in enumerate(s.lower()):
        for adj in _KEYBOARD.get(ch, ""):
            out.add(s[:i] + adj + s[i + 1 :])
    return out


def _homoglyph_subs(s: str) -> set[str]:
    out: set[str] = set()
    for i, ch in enumerate(s):
        sub = _HOMOGLYPHS.get(ch)
        if sub:
            out.add(s[:i] + sub + s[i + 1 :])
    return out


def _additions(s: str) -> set[str]:
    """Append one letter a-z at the end."""
    return {s + c for c in "abcdefghijklmnopqrstuvwxyz"}


def _hyphenations(s: str) -> set[str]:
    """Insert a hyphen at each interior position."""
    return {s[:i] + "-" + s[i:] for i in range(1, len(s))}


def generate_permutations(domain: str) -> PermutationReport:
    """Generate dnstwist-style typo / spoof permutations for ``domain``."""
    from .basic import normalise

    domain, sld, tld = normalise(domain)
    report = PermutationReport(sld=sld, tld=tld, base_domain=domain)

    if not sld or len(sld) < 3:
        report.notes.append("SLD too short or missing — permutation set skipped")
        return report

    seen: set[str] = {sld}
    # Order matters: more specific kinds (homoglyph, keyboard_adjacent) come
    # before the generic 'substitution' so their candidates are claimed by
    # the more meaningful label.
    generators: list[tuple[PermutationKind, "object"]] = [
        ("omission", _omissions),
        ("transposition", _transpositions),
        ("doubling", _doublings),
        ("homoglyph", _homoglyph_subs),
        ("keyboard_adjacent", _keyboard_adjacents),
        ("substitution", _substitutions),
        ("addition", _additions),
        ("hyphenation", _hyphenations),
    ]
    for kind, gen in generators:
        for variant in gen(sld):  # type: ignore[operator]
            if variant in seen or not variant or variant == sld:
                continue
            seen.add(variant)
            report.permutations.append(Permutation(candidate=variant, kind=kind))

    report.notes.append(
        f"generated {len(report.permutations)} permutations "
        f"(combine with `dpf check` per variant if you need availability probes)"
    )
    return report
