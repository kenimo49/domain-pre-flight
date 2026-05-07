"""RDAP-based domain lifecycle check (registration / expiry / registrar / status).

Uses the universal RDAP gateway at https://rdap.org/. RDAP is the IETF
successor to WHOIS — JSON-formatted, no auth required, well-defined schema.
The gateway routes the request to the authoritative server for the TLD.

Surfaces creation date, expiration date, last-changed date, registrar
name, and the registry status flags (e.g. ``clientHold``,
``redemptionPeriod``, ``serverDeleteProhibited``). Scoring penalises
expired-or-soon-to-expire domains and risky lifecycle states; new
registrations (<30 days) are flagged as a note rather than an issue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import requests

DEFAULT_TIMEOUT = 8
USER_AGENT = "domain-pre-flight/0.1 (+https://github.com/kenimo49/domain-pre-flight)"
RDAP_GATEWAY = "https://rdap.org/domain"

RdapStatus = Literal["ok", "lookup_failed", "not_found"]

# Risk-bearing registry status values (RFC 8056 / EPP).
RISKY_STATUSES = {
    "clientHold",
    "serverHold",
    "redemptionPeriod",
    "pendingDelete",
    "pendingTransfer",
    "inactive",
}


@dataclass
class RdapReport:
    domain: str
    status: RdapStatus = "ok"
    detail: str = ""
    created_at: str | None = None
    expires_at: str | None = None
    last_changed_at: str | None = None
    domain_age_days: int | None = None
    days_to_expiry: int | None = None
    registrar: str = ""
    domain_status: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _parse_event_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_registrar(entities: list[dict[str, Any]]) -> str:
    for entity in entities:
        roles = entity.get("roles") or []
        if "registrar" not in roles:
            continue
        # vcardArray is the standard place for the org name
        vcard = entity.get("vcardArray")
        if isinstance(vcard, list) and len(vcard) > 1:
            for field_ in vcard[1]:
                if isinstance(field_, list) and len(field_) >= 4 and field_[0] == "fn":
                    return str(field_[3])
        if entity.get("handle"):
            return str(entity["handle"])
    return ""


def check_rdap(domain: str, timeout: int = DEFAULT_TIMEOUT) -> RdapReport:
    """Query RDAP for the lifecycle metadata of ``domain``."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = RdapReport(domain=domain)

    if not sld:
        report.notes.append("no SLD parsed — RDAP check skipped")
        report.status = "lookup_failed"
        return report

    try:
        resp = requests.get(
            f"{RDAP_GATEWAY}/{domain}",
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json"},
        )
    except requests.RequestException as e:
        report.status = "lookup_failed"
        report.detail = f"transport: {e.__class__.__name__}"
        report.notes.append(f"RDAP query failed: {e.__class__.__name__}")
        return report

    if resp.status_code == 404:
        report.status = "not_found"
        report.detail = "RDAP returned 404 — domain likely unregistered"
        report.notes.append("RDAP 404 — domain appears available for registration")
        return report

    if resp.status_code != 200:
        report.status = "lookup_failed"
        report.detail = f"http {resp.status_code}"
        report.notes.append(f"RDAP returned http {resp.status_code}; verify manually")
        return report

    try:
        data = resp.json()
    except ValueError:
        report.status = "lookup_failed"
        report.detail = "non-JSON response"
        return report

    events = data.get("events") or []
    for event in events:
        action = event.get("eventAction")
        date = event.get("eventDate")
        if action == "registration":
            report.created_at = date
        elif action == "expiration":
            report.expires_at = date
        elif action == "last changed":
            report.last_changed_at = date

    now = datetime.now(timezone.utc)
    created = _parse_event_date(report.created_at)
    expires = _parse_event_date(report.expires_at)
    if created:
        report.domain_age_days = (now - created).days
    if expires:
        report.days_to_expiry = (expires - now).days

    statuses = data.get("status") or []
    report.domain_status = [str(s) for s in statuses]

    entities = data.get("entities") or []
    report.registrar = _extract_registrar(entities)

    risky_present = [s for s in report.domain_status if s in RISKY_STATUSES]
    if risky_present:
        report.issues.append(
            f"registry status flags risky lifecycle state: {', '.join(risky_present)}"
        )

    if report.days_to_expiry is not None:
        if report.days_to_expiry < 0:
            report.issues.append(
                f"domain has already expired ({-report.days_to_expiry} days ago)"
            )
        elif report.days_to_expiry < 30:
            report.issues.append(
                f"domain expires in {report.days_to_expiry} days — could drop into "
                "redemptionPeriod / pendingDelete shortly"
            )
        elif report.days_to_expiry < 90:
            report.notes.append(
                f"domain expires in {report.days_to_expiry} days — short runway"
            )

    if report.domain_age_days is not None and report.domain_age_days < 30:
        report.notes.append(
            f"domain registered only {report.domain_age_days} days ago — fresh registration"
        )

    return report
