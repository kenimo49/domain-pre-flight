"""Suggest related emerging-term domains alongside the main pre-flight check.

Requires the ``anthropic`` package and ``ANTHROPIC_API_KEY``::

    pip install domain-pre-flight[suggest]
    export ANTHROPIC_API_KEY=sk-...

The check:
1. Calls a small LLM to generate N related tech-term candidates based on the input SLD.
2. Verifies .com availability for each via RDAP (404 = likely available).
3. Fetches a 30-day Hacker News mention count for each term as a trend signal.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

DEFAULT_TIMEOUT = 8
HN_API = "https://hn.algolia.com/api/v1/search"
RDAP_GATEWAY = "https://rdap.org/domain"
USER_AGENT = "domain-pre-flight/suggest (+https://github.com/kenimo49/domain-pre-flight)"

_LLM_MODEL = "claude-haiku-4-5-20251001"
_SIGNAL_GREEN = 10
_SIGNAL_YELLOW = 3


@dataclass
class SuggestCandidate:
    term: str
    domain: str
    available: bool | None  # True=free, False=taken, None=RDAP inconclusive
    hn_mentions_30d: int
    signal: str  # "🟢" / "🟡" / "⚪" / "" (taken or unknown)


@dataclass
class SuggestReport:
    source_domain: str
    source_sld: str
    candidates: list[SuggestCandidate] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _hn_mentions(term: str, days: int = 30) -> int:
    cutoff = int(time.time()) - days * 86400
    try:
        r = requests.get(
            HN_API,
            params={
                "query": term,
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff}",
                "hitsPerPage": "0",
            },
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code == 200:
            return int(r.json().get("nbHits", 0))
    except Exception:
        pass
    return 0


def _rdap_available(domain: str) -> bool | None:
    """Return True if available, False if taken, None if inconclusive (rate-limit, timeout, etc.)."""
    try:
        r = requests.get(
            f"{RDAP_GATEWAY}/{domain}",
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json"},
        )
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            return False
        return None
    except Exception:
        return None


def _signal(mentions: int) -> str:
    if mentions >= _SIGNAL_GREEN:
        return "🟢"
    if mentions >= _SIGNAL_YELLOW:
        return "🟡"
    return "⚪"


def _generate_terms(sld: str, count: int) -> list[str]:
    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "anthropic package not installed — run: pip install domain-pre-flight[suggest]"
        ) from exc

    import os  # noqa: PLC0415

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"I'm registering the domain '{sld}.com'. "
        f"Generate exactly {count} short tech terms that are semantically related to '{sld}' "
        "and are likely to gain developer or startup attention in the next 30-90 days. "
        "Rules: lowercase only, no spaces, no hyphens, 4-14 characters, "
        "plausibly registrable as a .com domain, real compound words or portmanteaus preferred. "
        f"Output ONLY the {count} terms as a newline-separated list, nothing else."
    )
    msg = client.messages.create(
        model=_LLM_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    terms: list[str] = []
    for line in raw.splitlines():
        t = line.strip().lower().replace(" ", "").replace("-", "")
        if 4 <= len(t) <= 14 and t.isalnum():
            terms.append(t)
    return terms[:count]


def check_suggest(domain: str, *, count: int = 5) -> SuggestReport:
    """Generate emerging-term domain suggestions related to *domain*.

    Returns a :class:`SuggestReport`. If the ``anthropic`` package or
    ``ANTHROPIC_API_KEY`` are missing, the report contains an issue message
    and an empty candidates list — the caller can display this gracefully.
    """
    from .basic import normalise  # noqa: PLC0415

    domain, sld, _ = normalise(domain)
    report = SuggestReport(source_domain=domain, source_sld=sld)

    if not sld:
        report.issues.append("no SLD parsed — suggest skipped")
        return report

    try:
        terms = _generate_terms(sld, count)
    except (ImportError, EnvironmentError) as exc:
        report.issues.append(str(exc))
        return report
    except Exception:
        report.issues.append("LLM error: could not generate suggestions — check your API key and network")
        return report

    for term in terms:
        dot_com = f"{term}.com"
        available = _rdap_available(dot_com)
        mentions = _hn_mentions(term) if available is True else 0
        report.candidates.append(
            SuggestCandidate(
                term=term,
                domain=dot_com,
                available=available,
                hn_mentions_30d=mentions,
                signal=_signal(mentions) if available is True else "",
            )
        )

    available_count = sum(1 for c in report.candidates if c.available is True)
    if report.candidates and available_count == 0 and any(c.available is False for c in report.candidates):
        report.notes.append("all suggested .com domains are already registered")

    return report
