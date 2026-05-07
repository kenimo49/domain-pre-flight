"""Basic syntactic / structural checks for a domain name.

Deterministic, offline, no external network calls. The TLD risk *table* lives
here as raw data; how that table is converted into score deductions lives in
``score.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tldextract

# Per-TLD abuse-risk hint, sourced from Spamhaus "Top 10 Most Abused TLDs"
# and Interisle abuse studies. 0 = trusted, 70+ = heavily abused.
TLD_RISK = {
    "com": 0, "net": 0, "org": 0, "io": 0, "dev": 0, "ai": 0, "co": 5,
    "jp": 0, "uk": 0, "de": 0, "fr": 0, "us": 5,
    "app": 5, "blog": 5, "tech": 10,
    "site": 15, "store": 15, "online": 20, "shop": 15,
    "xyz": 30, "top": 40, "buzz": 40, "click": 50, "link": 30,
    "loan": 60, "work": 35, "icu": 50, "live": 25,
    "cf": 70, "ga": 70, "ml": 70, "tk": 70, "gq": 70,
}

LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

# Disable network calls so PSL refresh does not happen at runtime; the version
# bundled with the installed tldextract release is good enough for risk hints.
_extract = tldextract.TLDExtract(suffix_list_urls=())


@dataclass
class BasicReport:
    domain: str
    tld: str
    sld: str
    label_length: int
    hyphens: int
    digits: int
    has_idn: bool
    is_valid_syntax: bool
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.domain)


def parse_domain(domain: str) -> tuple[str, str]:
    """Return (sld_label, tld) using the Public Suffix List.

    For ``foo.example.co.jp`` this returns ``("example", "co.jp")``.
    """
    domain = domain.strip().lower().rstrip(".")
    if not domain:
        return "", ""
    parts = _extract(domain)
    return parts.domain, parts.suffix


def check_basic(domain: str) -> BasicReport:
    domain = domain.strip().lower().rstrip(".")
    sld, tld = parse_domain(domain)

    issues: list[str] = []
    notes: list[str] = []

    is_valid = bool(domain) and all(LABEL_RE.match(label) for label in domain.split("."))
    if not is_valid:
        issues.append("invalid hostname syntax (RFC 1035)")

    label_length = len(sld)
    if label_length < 3:
        issues.append("very short SLD (<3 chars) — typically reserved or premium")
    elif label_length > 20:
        issues.append("long SLD (>20 chars) — hard to remember")
    elif label_length > 15:
        notes.append("SLD longer than 15 chars — consider a shorter alternative")

    hyphens = sld.count("-")
    if hyphens >= 2:
        issues.append(f"{hyphens} hyphens in SLD — looks spammy / hard to dictate")
    elif hyphens == 1:
        notes.append("contains a hyphen — voice-spelling friction")

    digits = sum(c.isdigit() for c in sld)
    if digits >= 2:
        issues.append(f"{digits} digits in SLD — often correlates with spam patterns")
    elif digits == 1:
        notes.append("contains a digit — can be confused with a word (e.g., 4 vs for)")

    has_idn = any(ord(c) > 127 for c in domain) or "xn--" in domain
    if has_idn:
        notes.append("IDN / punycode detected — phishing risk perception, browser display varies")

    risk = tld_risk_for(tld)
    if risk >= 40:
        issues.append(f".{tld} is heavily abused — Spamhaus / SURBL high-risk tier")
    elif risk >= 20:
        notes.append(f".{tld} has elevated abuse rates — borderline, used by spam actors")

    return BasicReport(
        domain=domain,
        tld=tld,
        sld=sld,
        label_length=label_length,
        hyphens=hyphens,
        digits=digits,
        has_idn=has_idn,
        is_valid_syntax=is_valid,
        issues=issues,
        notes=notes,
    )


def tld_risk_for(tld: str) -> int:
    """Lookup the per-TLD risk hint. Unknown TLDs get a mild default penalty."""
    return TLD_RISK.get(tld, 25)
