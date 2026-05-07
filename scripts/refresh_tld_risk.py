#!/usr/bin/env python3
"""Refresh the bundled TLD-risk table at ``data/tld_risk.json``.

Behaviour:

1. Try to fetch a live abuse-statistics feed (currently: ICANN DAAR-derived
   public aggregations and the Interisle public reports).
2. If a fetch succeeds, normalise its TLD -> risk mapping onto the
   project's 0-70 scale and merge with the curated baseline.
3. Always write the result to ``src/domain_pre_flight/data/tld_risk.json``
   so that the next CI run picks it up.
4. If every live source fails, write the curated baseline unchanged so the
   bundle remains valid.

This script is intentionally conservative: an unrecognised feed shape, a
partial download, or a credentials-required endpoint is treated as a
fetch failure and falls back to the baseline. The script never silently
drops TLDs that are already in the bundle.

Usage:
    python scripts/refresh_tld_risk.py
    python scripts/refresh_tld_risk.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "src" / "domain_pre_flight" / "data" / "tld_risk.json"
USER_AGENT = "domain-pre-flight-refresh/0.1 (+https://github.com/kenimo49/domain-pre-flight)"

# Importing the package is safe even when tld_risk.json is missing — basic.py
# falls back to its embedded baseline. Sharing the table avoids two copies
# drifting apart.
sys.path.insert(0, str(REPO_ROOT / "src"))
from domain_pre_flight.checks.basic import _FALLBACK_TLD_RISK  # noqa: E402


def _baseline() -> dict[str, int]:
    return dict(_FALLBACK_TLD_RISK)


def _try_fetch_interisle(timeout: int = 15) -> dict[str, int] | None:
    """Best-effort fetch of an Interisle phishing report aggregation, if a
    machine-readable form ever becomes available. The actual reports are
    PDFs today, so this branch returns None for now."""
    return None


def _try_fetch_dnsabuse_csv(timeout: int = 15) -> dict[str, int] | None:
    """Optional: fetch dnsabuseinstitute / DAAR-derived public CSVs, if any
    new public source appears. Currently a no-op."""
    return None


def merge(baseline: dict[str, int], live: dict[str, int]) -> dict[str, int]:
    """Merge live values onto the baseline. Live values *override* baseline,
    but TLDs only present in baseline are preserved (we do not silently
    forget the curated knowledge)."""
    out = dict(baseline)
    for tld, score in live.items():
        out[tld.lower()] = max(0, min(70, int(score)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print result, do not write file")
    args = parser.parse_args()

    sources = ["Spamhaus 'Top 10 Most Abused TLDs' historical aggregates",
               "Interisle Consulting phishing/malware studies",
               "Manual curation (kenimo49/domain-pre-flight maintainers)"]

    risk = _baseline()

    interisle = _try_fetch_interisle()
    if interisle:
        risk = merge(risk, interisle)
        sources.insert(0, "Interisle Consulting phishing report (live)")

    dnsabuse = _try_fetch_dnsabuse_csv()
    if dnsabuse:
        risk = merge(risk, dnsabuse)
        sources.insert(0, "DNS Abuse Institute aggregates (live)")

    payload = {
        "version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sources": sources,
        "scale": "0 = trusted; 70 = heavily abused. Unknown TLDs default to 25.",
        "risk": dict(sorted(risk.items())),
    }

    if args.dry_run:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET} ({len(risk)} TLDs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
