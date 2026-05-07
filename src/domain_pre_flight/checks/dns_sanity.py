"""DNS hygiene check: MX, SPF, DMARC, DKIM presence.

Probes whether the candidate domain has the email-authentication
infrastructure that legitimate operations typically deploy. For an
unregistered candidate this check is informational (everything will be
absent); for a domain you are evaluating to acquire, missing SPF / DMARC
are signals that the previous owner had loose hygiene and the domain may
have been spoofable / spammable.

This module never blocks on a single slow nameserver — each lookup uses
a short timeout and failures are folded into ``unknown`` results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import dns.exception
import dns.resolver

LookupOutcome = Literal["present", "absent", "unknown"]

DEFAULT_TIMEOUT = 4.0
COMMON_DKIM_SELECTORS = ("default", "google", "selector1", "selector2", "s1", "s2", "k1")


@dataclass
class DnsSanityReport:
    domain: str
    mx: LookupOutcome = "unknown"
    spf: LookupOutcome = "unknown"
    dmarc: LookupOutcome = "unknown"
    dkim: LookupOutcome = "unknown"
    mx_records: list[str] = field(default_factory=list)
    spf_record: str = ""
    dmarc_record: str = ""
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _resolver(timeout: float) -> dns.resolver.Resolver:
    res = dns.resolver.Resolver()
    res.timeout = timeout
    res.lifetime = timeout
    return res


def _lookup_mx(domain: str, timeout: float) -> tuple[LookupOutcome, list[str]]:
    try:
        answer = _resolver(timeout).resolve(domain, "MX")
        records = sorted(str(rr.exchange).rstrip(".") for rr in answer)
        return ("present" if records else "absent", records)
    except dns.resolver.NoAnswer:
        return ("absent", [])
    except dns.resolver.NXDOMAIN:
        return ("absent", [])
    except (dns.exception.DNSException, OSError):
        return ("unknown", [])


def _lookup_txt(domain: str, timeout: float) -> tuple[LookupOutcome, list[str]]:
    try:
        answer = _resolver(timeout).resolve(domain, "TXT")
        records = []
        for rr in answer:
            chunks = [c.decode("utf-8", errors="replace") for c in rr.strings]
            records.append("".join(chunks))
        return ("present" if records else "absent", records)
    except dns.resolver.NoAnswer:
        return ("absent", [])
    except dns.resolver.NXDOMAIN:
        return ("absent", [])
    except (dns.exception.DNSException, OSError):
        return ("unknown", [])


def _find_record(records: list[str], prefix: str) -> str:
    for rec in records:
        if rec.lower().startswith(prefix.lower()):
            return rec
    return ""


def check_dns_sanity(domain: str, *, timeout: float = DEFAULT_TIMEOUT) -> DnsSanityReport:
    """Probe MX, SPF, DMARC, DKIM presence for ``domain``."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = DnsSanityReport(domain=domain)

    if not sld:
        report.notes.append("no SLD parsed — DNS sanity skipped")
        return report

    # MX
    mx_outcome, mx_records = _lookup_mx(domain, timeout)
    report.mx = mx_outcome
    report.mx_records = mx_records

    # TXT records on apex; SPF lives here
    apex_outcome, apex_records = _lookup_txt(domain, timeout)
    spf_record = _find_record(apex_records, "v=spf1")
    if spf_record:
        report.spf = "present"
        report.spf_record = spf_record
    elif apex_outcome == "unknown":
        report.spf = "unknown"
    else:
        report.spf = "absent"

    # DMARC lives on _dmarc.<domain>
    dmarc_outcome, dmarc_records = _lookup_txt(f"_dmarc.{domain}", timeout)
    dmarc_record = _find_record(dmarc_records, "v=DMARC1")
    if dmarc_record:
        report.dmarc = "present"
        report.dmarc_record = dmarc_record
    elif dmarc_outcome == "unknown":
        report.dmarc = "unknown"
    else:
        report.dmarc = "absent"

    # DKIM heuristic: probe a few common selectors. Any one being present is enough.
    dkim_seen_unknown = False
    dkim_present = False
    for selector in COMMON_DKIM_SELECTORS:
        sub = f"{selector}._domainkey.{domain}"
        outcome, records = _lookup_txt(sub, timeout)
        if outcome == "present" and any("v=DKIM1" in r or "p=" in r for r in records):
            dkim_present = True
            break
        if outcome == "unknown":
            dkim_seen_unknown = True
    if dkim_present:
        report.dkim = "present"
    elif dkim_seen_unknown:
        report.dkim = "unknown"
    else:
        report.dkim = "absent"

    if report.mx == "present" and report.spf == "absent":
        report.issues.append(
            "MX configured but no SPF record — domain is likely spoofable; "
            "if buying this domain, the previous owner had loose hygiene"
        )
    if report.mx == "present" and report.dmarc == "absent":
        report.issues.append(
            "MX configured but no DMARC record — recipient mail systems will not "
            "enforce sender authentication; spoofing risk"
        )

    if report.mx == "absent":
        report.notes.append("no MX records — domain does not currently receive email")
    if report.spf == "absent" and report.mx == "absent":
        report.notes.append("no SPF record (consistent with no email setup)")

    return report
