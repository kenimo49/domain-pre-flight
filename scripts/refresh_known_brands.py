#!/usr/bin/env python3
"""Refresh the bundled brand list at ``data/known_brands.txt``.

Source: the Tranco list (https://tranco-list.eu/, CC BY 4.0). We pull the
latest top-N domains, strip their TLDs to produce brand stems, and merge
with the curated baseline (the human-edited entries already in the file).

Behaviour:

1. Try to fetch a fresh Tranco snapshot.
2. If the fetch succeeds, take the top-N domains, strip TLDs via
   ``tldextract``, deduplicate, and union with the curated baseline.
3. If the fetch fails (network down, list URL changed), leave the file
   untouched and exit non-zero so CI surfaces the failure.
4. Always preserve the curated baseline section at the top of the file.

Usage:
    python scripts/refresh_known_brands.py
    python scripts/refresh_known_brands.py --top 5000
    python scripts/refresh_known_brands.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

import requests
import tldextract

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "src" / "domain_pre_flight" / "data" / "known_brands.txt"
TRANCO_LATEST_URL = "https://tranco-list.eu/top-1m.csv.zip"
USER_AGENT = "domain-pre-flight-refresh/0.1 (+https://github.com/kenimo49/domain-pre-flight)"

# Brand stems shorter than this are exempt from typosquat similarity matching
# anyway, so don't pollute the list with them.
MIN_STEM_LENGTH = 4


def _read_curated_baseline(path: Path) -> tuple[list[str], set[str]]:
    """Return (lines_to_preserve_verbatim, stems_already_present).

    Lines preserved verbatim include headers/comments and section dividers.
    The set is used to suppress duplicates from the Tranco fetch.
    """
    lines: list[str] = []
    stems: set[str] = set()
    if not path.exists():
        return lines, stems
    for raw in path.read_text(encoding="utf-8").splitlines():
        lines.append(raw)
        s = raw.strip()
        if s and not s.startswith("#"):
            stems.add(s.lower())
    return lines, stems


def _fetch_tranco_top_n(top_n: int, timeout: int = 60) -> list[str]:
    """Fetch the latest Tranco list and return the top-N domain strings."""
    resp = requests.get(
        TRANCO_LATEST_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        members = zf.namelist()
        csv_member = next((m for m in members if m.endswith(".csv")), None)
        if csv_member is None:
            raise RuntimeError(f"Tranco zip lacks a CSV member; found {members}")
        with zf.open(csv_member) as fh:
            text = fh.read().decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    out: list[str] = []
    for row in reader:
        if len(row) < 2:
            continue
        out.append(row[1].strip().lower())
        if len(out) >= top_n:
            break
    return out


def _stems_from_domains(domains: list[str]) -> list[str]:
    extract = tldextract.TLDExtract(suffix_list_urls=())
    stems: list[str] = []
    seen: set[str] = set()
    for d in domains:
        parts = extract(d)
        stem = parts.domain.lower()
        if len(stem) < MIN_STEM_LENGTH:
            continue
        if stem in seen:
            continue
        seen.add(stem)
        stems.append(stem)
    return stems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=2000, help="Top-N from Tranco (default 2000).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    baseline_lines, baseline_stems = _read_curated_baseline(TARGET)

    try:
        domains = _fetch_tranco_top_n(args.top)
    except (requests.RequestException, RuntimeError, zipfile.BadZipFile) as e:
        print(f"Tranco fetch failed: {e}", file=sys.stderr)
        return 1

    fresh_stems = _stems_from_domains(domains)
    new_stems = [s for s in fresh_stems if s not in baseline_stems]

    section_header = "\n# Tranco-derived stems (auto-refreshed; do not edit by hand)"

    if args.dry_run:
        print(f"would add {len(new_stems)} new stems below the curated baseline")
        for s in new_stems[:20]:
            print(f"  {s}")
        if len(new_stems) > 20:
            print(f"  ... and {len(new_stems) - 20} more")
        return 0

    out_lines = list(baseline_lines)
    if new_stems:
        out_lines.append(section_header)
        out_lines.extend(new_stems)
    TARGET.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET} ({len(new_stems)} new stems added; total now ~{len(baseline_stems) + len(new_stems)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
