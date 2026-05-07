"""IDN homograph attack detection (UTS #39 confusables).

basic.py only flags whether an SLD is an IDN; this module decides whether
the IDN visually mimics a Latin-script brand. The signal is "this domain
could be used to phish users of <brand>" — a strictly stronger statement
than "this domain has non-ASCII characters."

Approach: ask the ``confusable-homoglyphs`` library (UTS #39 confusable
data) for character-level confusables, build the de-confused Latin form
of the SLD, and check whether that form matches a known brand stem from
the typosquat brand list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from confusable_homoglyphs import confusables

ConfusableSeverity = Literal["clean", "confusable", "brand_collision"]


@dataclass
class HomographReport:
    domain: str
    sld: str
    is_idn: bool = False
    has_confusables: bool = False
    de_confused: str = ""
    brand_collision: str = ""
    severity: ConfusableSeverity = "clean"
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _de_confuse(sld: str) -> str:
    """Replace **non-Latin** confusable characters with their Latin equivalents.

    Pure-Latin SLDs return unchanged even if their characters happen to be
    listed as confusables for other scripts (the goal is to detect non-Latin
    spoofs of Latin brands, not to over-rewrite legitimate Latin text).
    """
    findings = confusables.is_confusable(sld, greedy=True)
    if not findings:
        return sld

    out = sld
    for f in findings:
        char = f["character"]
        if ord(char) < 128:
            continue
        latin = next(
            (h["c"] for h in f.get("homoglyphs", []) if "LATIN" in h.get("n", "")),
            None,
        )
        if latin and len(latin) == 1:
            out = out.replace(char, latin)
    return out


def check_idn_homograph(
    domain: str,
    *,
    brands: list[str] | None = None,
) -> HomographReport:
    """Detect whether the SLD is a homograph spoof of a known Latin brand."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = HomographReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — homograph check skipped")
        return report

    is_idn = any(ord(c) > 127 for c in sld) or "xn--" in sld
    report.is_idn = is_idn
    if not is_idn:
        return report

    findings = confusables.is_confusable(sld, greedy=True)
    if not findings:
        report.notes.append("IDN present but no confusable characters detected")
        return report

    report.has_confusables = True
    report.severity = "confusable"
    report.de_confused = _de_confuse(sld)

    if brands is None:
        from .typosquat import load_brands

        brands = load_brands()
    brand_set = {b.lower() for b in brands}

    if report.de_confused in brand_set and report.de_confused != sld:
        report.brand_collision = report.de_confused
        report.severity = "brand_collision"
        report.issues.append(
            f"IDN homograph: SLD visually mimics known brand '{report.de_confused}' "
            "(de-confused form) — phishing risk, do not register"
        )
    else:
        report.notes.append(
            f"confusable characters detected; de-confused form is '{report.de_confused}' "
            "— review whether this resembles a real brand"
        )

    return report
