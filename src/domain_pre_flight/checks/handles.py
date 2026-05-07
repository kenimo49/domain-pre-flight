"""Same-name availability checks across developer platforms and social networks.

Each platform check returns one of three states:

- ``taken``     — a profile/package with this name exists
- ``available`` — confirmed not present
- ``unknown``   — could not determine (rate limit, bot wall, transport error)

Platforms with aggressive bot protection (X, Instagram) frequently return
``unknown``; the CLI surfaces that explicitly so the user is not misled.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Literal

import requests

HandleStatus = Literal["taken", "available", "unknown"]

DEFAULT_TIMEOUT = 6
USER_AGENT = "domain-pre-flight/0.1 (+https://github.com/kenimo49/domain-pre-flight)"


@dataclass
class HandleResult:
    platform: str
    status: HandleStatus
    detail: str = ""


@dataclass
class HandleReport:
    domain: str
    sld: str
    results: list[HandleResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _request(method: str, url: str, timeout: int) -> requests.Response | None:
    try:
        return requests.request(
            method,
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
        )
    except requests.RequestException:
        return None


def check_github(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("GET", f"https://api.github.com/users/{name}", timeout)
    if resp is None:
        return HandleResult("github", "unknown", "transport error")
    if resp.status_code == 200:
        return HandleResult("github", "taken")
    if resp.status_code == 404:
        return HandleResult("github", "available")
    if resp.status_code == 403:
        return HandleResult("github", "unknown", "rate-limited (anonymous 60/hr)")
    return HandleResult("github", "unknown", f"http {resp.status_code}")


def check_npm(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("GET", f"https://registry.npmjs.org/{name}", timeout)
    if resp is None:
        return HandleResult("npm", "unknown", "transport error")
    if resp.status_code == 200:
        return HandleResult("npm", "taken")
    if resp.status_code == 404:
        return HandleResult("npm", "available")
    return HandleResult("npm", "unknown", f"http {resp.status_code}")


def check_pypi(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("GET", f"https://pypi.org/pypi/{name}/json", timeout)
    if resp is None:
        return HandleResult("pypi", "unknown", "transport error")
    if resp.status_code == 200:
        return HandleResult("pypi", "taken")
    if resp.status_code == 404:
        return HandleResult("pypi", "available")
    return HandleResult("pypi", "unknown", f"http {resp.status_code}")


def check_twitter(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("HEAD", f"https://twitter.com/{name}", timeout)
    if resp is None:
        return HandleResult("twitter", "unknown", "transport error")
    # Twitter blocks anonymous HEAD requests for taken profiles too; treat any
    # non-404 as inconclusive rather than risk reporting "available" for a
    # name that really is taken.
    if resp.status_code == 404:
        return HandleResult("twitter", "available")
    return HandleResult("twitter", "unknown", "bot protection — verify in browser")


def check_instagram(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("HEAD", f"https://www.instagram.com/{name}/", timeout)
    if resp is None:
        return HandleResult("instagram", "unknown", "transport error")
    if resp.status_code == 404:
        return HandleResult("instagram", "available")
    return HandleResult("instagram", "unknown", "bot protection — verify in browser")


# Public registry of platform checkers. Tests can monkeypatch this.
PLATFORM_CHECKS: dict[str, Callable[[str, int], HandleResult]] = {
    "github": check_github,
    "npm": check_npm,
    "pypi": check_pypi,
    "twitter": check_twitter,
    "instagram": check_instagram,
}


def check_handles(
    domain: str,
    *,
    platforms: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_workers: int = 5,
) -> HandleReport:
    """Fan out same-name availability checks across the requested platforms.

    The SLD (left-most label of the domain) is used as the candidate handle.
    """
    from .basic import parse_domain

    domain = domain.strip().lower().rstrip(".")
    sld, _ = parse_domain(domain)
    report = HandleReport(domain=domain, sld=sld)

    if not sld:
        report.notes.append("no SLD parsed — handle lookup skipped")
        return report

    selected = platforms or list(PLATFORM_CHECKS.keys())
    unknown_platforms = [p for p in selected if p not in PLATFORM_CHECKS]
    if unknown_platforms:
        report.notes.append(f"ignored unknown platforms: {', '.join(unknown_platforms)}")
    selected = [p for p in selected if p in PLATFORM_CHECKS]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(PLATFORM_CHECKS[p], sld, timeout): p for p in selected}
        for future in futures:
            report.results.append(future.result())

    report.results.sort(key=lambda r: r.platform)

    taken = [r.platform for r in report.results if r.status == "taken"]
    if taken:
        report.notes.append(f"{len(taken)} platform(s) already taken: {', '.join(taken)}")

    return report
