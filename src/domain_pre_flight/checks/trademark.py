"""Trademark conflict check across USPTO (US), EUIPO (EU), and J-PlatPat (JP).

**Implementation note (v0.7.1)**: every jurisdiction is now ``not_supported``;
the report exposes a pre-filled deeplink for manual verification instead of
attempting a live query. See ``docs/decisions/0009-trademark-deeplink-only.md``
for the rationale — public, documented, no-auth search APIs do not currently
exist for any of the three registries we care about, so attempting them
returned ``lookup_failed`` for almost every domain we tested.

The data structures and the public entry point are unchanged so callers
that previously consumed ``TrademarkReport`` keep working; only the
``status`` and ``deeplink`` semantics shifted.

This tool surfaces *candidates*, not legal opinions. "Confusingly similar"
is a legal standard, not a string-distance threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote_plus

JurisdictionStatus = Literal["ok", "lookup_failed", "not_supported"]
Similarity = Literal["exact", "similar"]


@dataclass
class TrademarkMatch:
    mark: str
    owner: str = ""
    status_text: str = ""
    serial: str = ""
    classes: list[str] = field(default_factory=list)
    similarity: Similarity = "exact"


@dataclass
class JurisdictionResult:
    jurisdiction: str
    status: JurisdictionStatus
    detail: str = ""
    matches: list[TrademarkMatch] = field(default_factory=list)
    deeplink: str = ""


@dataclass
class TrademarkReport:
    domain: str
    sld: str
    jurisdictions: list[JurisdictionResult] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def has_exact_match(self) -> bool:
        return any(
            any(m.similarity == "exact" for m in j.matches)
            for j in self.jurisdictions
        )


_DEEPLINK_TEMPLATES: dict[str, tuple[str, str]] = {
    "us": (
        "https://tmsearch.uspto.gov/search/search-information?q={q}",
        "USPTO has no public, documented search API; verify manually",
    ),
    "eu": (
        "https://www.tmdn.org/tmview/#/tmview/results?text={q}",
        "EUIPO TMview has no stable public search API; verify manually",
    ),
    "jp": (
        "https://www.j-platpat.inpit.go.jp/t0100?term={q}",
        "J-PlatPat has no public query API; verify manually",
    ),
}


def _deeplink_for(jurisdiction: str, sld: str) -> JurisdictionResult:
    template, detail = _DEEPLINK_TEMPLATES[jurisdiction]
    return JurisdictionResult(
        jurisdiction=jurisdiction,
        status="not_supported",
        detail=detail,
        deeplink=template.format(q=quote_plus(sld)),
    )


def check_trademark(
    domain: str,
    *,
    jurisdictions: list[str] | None = None,
    timeout: int = 10,  # kept for backward compatibility, unused
    max_workers: int = 1,  # kept for backward compatibility, unused
) -> TrademarkReport:
    """Return a TrademarkReport with deeplinks for manual verification.

    All jurisdictions resolve synchronously with ``status="not_supported"``.
    No network call is made; the user follows the deeplink to verify.
    """
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = TrademarkReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — trademark check skipped")
        return report

    selected = jurisdictions or list(_DEEPLINK_TEMPLATES.keys())
    unknown = [j for j in selected if j not in _DEEPLINK_TEMPLATES]
    if unknown:
        report.notes.append(f"ignored unknown jurisdictions: {', '.join(unknown)}")
    selected = [j for j in selected if j in _DEEPLINK_TEMPLATES]

    for j in selected:
        report.jurisdictions.append(_deeplink_for(j, sld))

    report.jurisdictions.sort(key=lambda j: j.jurisdiction)
    report.notes.append(
        "trademark queries surface deeplinks only — open each link to verify "
        "manually. See docs/decisions/0009-trademark-deeplink-only.md."
    )
    return report
