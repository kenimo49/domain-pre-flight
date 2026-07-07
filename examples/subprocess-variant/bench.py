"""Benchmark: library-direct vs subprocess MCP tool implementations.

Two measurements:
1. offline (list_typo_permutations) — isolates pure subprocess overhead
   (interpreter startup + imports + JSON round-trip), no network noise.
2. online (check_domain, includes Wayback lookup) — overhead relative to a
   realistic workload.

Usage: python examples/subprocess-variant/bench.py [--runs 20] [--domain example.com]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from collections.abc import Callable

from domain_pre_flight import mcp_server


def _time(fn: Callable[[], object], runs: int) -> list[float]:
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return samples


def _cli(args: list[str]) -> dict:
    proc = subprocess.run(
        ["domain-pre-flight", *args, "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return json.loads(proc.stdout)


def _report(label: str, samples: list[float]) -> None:
    print(
        f"{label:<38} n={len(samples):>3}  "
        f"mean={statistics.mean(samples):>8.1f}ms  "
        f"median={statistics.median(samples):>8.1f}ms  "
        f"min={min(samples):>8.1f}ms  max={max(samples):>8.1f}ms"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--online-runs", type=int, default=5)
    parser.add_argument("--domain", default="example.com")
    args = parser.parse_args()

    print(f"domain={args.domain}\n")

    print("--- offline: list_typo_permutations (pure overhead) ---")
    _report(
        "library-direct",
        _time(lambda: mcp_server.list_typo_permutations(args.domain, limit=50), args.runs),
    )
    _report(
        "subprocess",
        _time(lambda: _cli(["permutations", args.domain, "--limit", "50"]), args.runs),
    )

    print("\n--- online: check_domain (realistic workload, incl. Wayback) ---")
    _report(
        "library-direct",
        _time(lambda: mcp_server.check_domain(args.domain), args.online_runs),
    )
    _report(
        "subprocess",
        _time(lambda: _cli(["check", args.domain]), args.online_runs),
    )


if __name__ == "__main__":
    main()
