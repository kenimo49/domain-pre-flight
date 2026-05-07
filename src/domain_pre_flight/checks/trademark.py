"""Trademark conflict check across USPTO (US), J-PlatPat (JP), and EUIPO (EU).

Each jurisdiction is queried independently and may return one of:

- ``ok``               — query succeeded, results are populated (possibly empty)
- ``lookup_failed``    — transport / API error; the user should retry or
                         consult the registry directly
- ``not_supported``    — no public, redistributable query path is available;
                         we surface a deep-link to the official search UI so
                         the user can verify manually

This module surfaces *candidates*, not legal opinions. "Confusingly similar"
is a legal standard, not a string-distance threshold.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT = 12
USER_AGENT = "domain-pre-flight/0.1 (+https://github.com/kenimo49/domain-pre-flight)"

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


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    # 5xx responses from public registries are common at peak load; one retry
    # with backoff turns a flaky lookup into a soft success without doubling
    # the worst-case wait for a real outage.
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _query_uspto(name: str, session: requests.Session, timeout: int) -> JurisdictionResult:
    """USPTO Trademark Search API (developer.uspto.gov)."""
    deeplink = f"https://tmsearch.uspto.gov/search/search-information?q={name}"
    url = "https://tmsearch.uspto.gov/api/search/case"
    params = {
        "searchText": name,
        "rows": 25,
        "fromIndex": 0,
    }
    try:
        resp = session.get(url, params=params, timeout=timeout)
    except requests.RequestException as e:
        return JurisdictionResult("us", "lookup_failed", f"transport: {e.__class__.__name__}", deeplink=deeplink)

    if resp.status_code != 200:
        return JurisdictionResult(
            "us", "lookup_failed", f"http {resp.status_code}", deeplink=deeplink
        )

    matches: list[TrademarkMatch] = []
    try:
        data = resp.json()
        hits = data.get("hits", {}).get("hits", []) or data.get("results", []) or []
        for hit in hits[:10]:
            src = hit.get("_source", hit) if isinstance(hit, dict) else {}
            mark = (src.get("markIdentification") or src.get("mark") or "").strip()
            if not mark:
                continue
            matches.append(
                TrademarkMatch(
                    mark=mark,
                    owner=(src.get("ownerName") or src.get("owner") or "").strip(),
                    status_text=(src.get("statusDesc") or src.get("status") or "").strip(),
                    serial=str(src.get("serialNumber") or src.get("serial") or ""),
                    classes=list(src.get("internationalClass") or []),
                    similarity="exact" if mark.lower() == name.lower() else "similar",
                )
            )
    except (ValueError, KeyError, TypeError):
        return JurisdictionResult(
            "us", "lookup_failed", "unrecognised response shape", deeplink=deeplink
        )

    return JurisdictionResult("us", "ok", matches=matches, deeplink=deeplink)


def _query_euipo(name: str, session: requests.Session, timeout: int) -> JurisdictionResult:
    """EUIPO TMview public search API."""
    deeplink = f"https://www.tmdn.org/tmview/#/tmview/results?text={name}"
    url = "https://www.tmdn.org/tmview/api/search/results"
    payload = {
        "page": 1,
        "pageSize": 25,
        "criteria": "C",
        "basicSearch": name,
    }
    try:
        resp = session.post(url, json=payload, timeout=timeout)
    except requests.RequestException as e:
        return JurisdictionResult("eu", "lookup_failed", f"transport: {e.__class__.__name__}", deeplink=deeplink)

    if resp.status_code != 200:
        return JurisdictionResult(
            "eu", "lookup_failed", f"http {resp.status_code}", deeplink=deeplink
        )

    matches: list[TrademarkMatch] = []
    try:
        data = resp.json()
        for hit in (data.get("tradeMarks") or [])[:10]:
            mark = (hit.get("tmName") or "").strip()
            if not mark:
                continue
            matches.append(
                TrademarkMatch(
                    mark=mark,
                    owner=(hit.get("applicantName") or "").strip(),
                    status_text=(hit.get("status") or "").strip(),
                    serial=str(hit.get("applicationNumber") or ""),
                    classes=[str(c) for c in (hit.get("niceClass") or [])],
                    similarity="exact" if mark.lower() == name.lower() else "similar",
                )
            )
    except (ValueError, KeyError, TypeError):
        return JurisdictionResult(
            "eu", "lookup_failed", "unrecognised response shape", deeplink=deeplink
        )

    return JurisdictionResult("eu", "ok", matches=matches, deeplink=deeplink)


def _query_jplatpat(name: str, session: requests.Session, timeout: int) -> JurisdictionResult:
    """J-PlatPat has no public API. Surface a deep-link for manual review."""
    deeplink = f"https://www.j-platpat.inpit.go.jp/t0100?term={name}"
    return JurisdictionResult(
        "jp",
        "not_supported",
        "J-PlatPat has no public query API — open the deeplink to verify manually",
        deeplink=deeplink,
    )


_QUERIES = {
    "us": _query_uspto,
    "eu": _query_euipo,
    "jp": _query_jplatpat,
}

# J-PlatPat resolves synchronously (no public API, deeplink only); keeping it
# out of the executor leaves the pool sized to actual network workers.
_NETWORK_QUERIES = frozenset({"us", "eu"})


def check_trademark(
    domain: str,
    *,
    jurisdictions: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int = 2,
) -> TrademarkReport:
    """Fan out trademark queries across the requested jurisdictions."""
    from .basic import normalise

    domain, sld, _ = normalise(domain)
    report = TrademarkReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — trademark check skipped")
        return report

    selected = jurisdictions or list(_QUERIES.keys())
    unknown = [j for j in selected if j not in _QUERIES]
    if unknown:
        report.notes.append(f"ignored unknown jurisdictions: {', '.join(unknown)}")
    selected = [j for j in selected if j in _QUERIES]

    session = _session()
    network_jurisdictions = [j for j in selected if j in _NETWORK_QUERIES]
    sync_jurisdictions = [j for j in selected if j not in _NETWORK_QUERIES]

    if network_jurisdictions:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_QUERIES[j], sld, session, timeout) for j in network_jurisdictions
            ]
            for f in futures:
                report.jurisdictions.append(f.result())
    for j in sync_jurisdictions:
        report.jurisdictions.append(_QUERIES[j](sld, session, timeout))

    report.jurisdictions.sort(key=lambda j: j.jurisdiction)

    exact_jurisdictions: list[str] = []
    similar_jurisdictions: list[str] = []
    failed_jurisdictions: list[str] = []
    for j in report.jurisdictions:
        if j.status == "lookup_failed":
            failed_jurisdictions.append(j.jurisdiction)
        if any(m.similarity == "exact" for m in j.matches):
            exact_jurisdictions.append(j.jurisdiction)
        elif j.matches:
            similar_jurisdictions.append(j.jurisdiction)

    if exact_jurisdictions:
        report.issues.append(
            f"exact trademark match in: {', '.join(exact_jurisdictions)} — UDRP / infringement risk. "
            "This tool flags candidates; consult counsel before proceeding."
        )
    if similar_jurisdictions:
        report.notes.append(
            f"similar marks found in: {', '.join(similar_jurisdictions)} — review the results before deciding."
        )
    if failed_jurisdictions:
        report.notes.append(
            f"could not query: {', '.join(failed_jurisdictions)} — verify manually using the provided deeplinks."
        )

    return report
