"""Basic syntactic / structural checks for a domain name.

These checks are deterministic, offline, and free of external API calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# TLD risk tiers: lower score = higher risk.
# Sources: Spamhaus "Top 10 Most Abused TLDs", Interisle abuse studies, anecdotal SEO data.
TLD_RISK = {
    # Trusted, mainstream
    "com": 0,
    "net": 0,
    "org": 0,
    "io": 0,
    "dev": 0,
    "ai": 0,
    "co": 5,
    # Country-code, well-managed
    "jp": 0,
    "uk": 0,
    "de": 0,
    "fr": 0,
    "us": 5,
    # New gTLD, mostly fine but some abuse
    "app": 5,
    "blog": 5,
    "tech": 10,
    "site": 15,
    "store": 15,
    "online": 20,
    "shop": 15,
    # Frequently flagged for abuse
    "xyz": 30,
    "top": 40,
    "buzz": 40,
    "click": 50,
    "link": 30,
    "loan": 60,
    "work": 35,
    "icu": 50,
    "live": 25,
    "cf": 70,
    "ga": 70,
    "ml": 70,
    "tk": 70,
    "gq": 70,
}

# Hostname label rules: RFC 1035 + practical limits.
LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


@dataclass
class BasicReport:
    domain: str
    tld: str
    sld: str
    length: int
    label_length: int
    hyphens: int
    digits: int
    has_idn: bool
    is_valid_syntax: bool
    tld_risk_score: int
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_domain(domain: str) -> tuple[str, str]:
    """Return (sld_label, tld) for a domain. Naive single-label TLD split.

    For multi-label TLDs like ``co.jp`` we only strip the last label; this is
    fine for the heuristic scoring used here.
    """
    domain = domain.strip().lower().rstrip(".")
    if "." not in domain:
        return domain, ""
    sld, _, tld = domain.rpartition(".")
    return sld, tld


def check_basic(domain: str) -> BasicReport:
    """Perform offline structural checks on a domain string."""
    domain = domain.strip().lower().rstrip(".")
    sld, tld = parse_domain(domain)

    issues: list[str] = []
    notes: list[str] = []

    # Validate syntactic correctness label-by-label.
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

    has_idn = any(ord(c) > 127 for c in domain) or domain.startswith("xn--") or "xn--" in domain
    if has_idn:
        notes.append("IDN / punycode detected — phishing risk perception, browser display varies")

    tld_risk_score = TLD_RISK.get(tld, 25)  # unknown TLD = mild penalty by default
    if tld_risk_score >= 40:
        issues.append(f".{tld} is heavily abused — Spamhaus / SURBL high-risk tier")
    elif tld_risk_score >= 20:
        notes.append(f".{tld} has elevated abuse rates — borderline, used by spam actors")

    return BasicReport(
        domain=domain,
        tld=tld,
        sld=sld,
        length=len(domain),
        label_length=label_length,
        hyphens=hyphens,
        digits=digits,
        has_idn=has_idn,
        is_valid_syntax=is_valid,
        tld_risk_score=tld_risk_score,
        issues=issues,
        notes=notes,
    )
