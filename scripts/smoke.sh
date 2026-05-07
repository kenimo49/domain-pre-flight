#!/usr/bin/env bash
#
# CLI smoke tests for domain-pre-flight.
#
# Walks a small fixture set of representative domains and asserts that the
# verdict band and CLI exit code match what we expect from the v0.1 scoring
# rules. Useful as a coarse regression check after touching the score table
# or the CLI plumbing.
#
# Usage:
#   bash scripts/smoke.sh              # full run, includes Wayback history calls
#   bash scripts/smoke.sh --offline    # skip the Wayback path (fast, deterministic)
#
# Exits non-zero on the first mismatch.

set -euo pipefail

OFFLINE=0
if [[ "${1:-}" == "--offline" ]]; then
  OFFLINE=1
fi

# Resolve the CLI: prefer the venv binary if present, otherwise fall back to
# whatever is on PATH (matches what `pip install -e .` exposes in CI).
if [[ -x ".venv/bin/domain-pre-flight" ]]; then
  CLI=".venv/bin/domain-pre-flight"
elif command -v domain-pre-flight >/dev/null 2>&1; then
  CLI="domain-pre-flight"
else
  echo "FAIL: domain-pre-flight CLI not found (install with 'pip install -e .' first)" >&2
  exit 1
fi

PASS=0
FAIL=0
FAILED_CASES=()

# Each case is: domain | expected_band | expected_exit_code
# Bands: GREEN(exit 0), YELLOW(exit 0), ORANGE(exit 1), RED(exit 2)
CASES=(
  "example.com|GREEN|0"
  "nicebrand.com|GREEN|0"
  "myapp.io|GREEN|0"
  "myapp.dev|GREEN|0"
  "buy-cheap-2024-deals.tk|RED|2"
  "spammy-loans.loan|RED|2"
  "-invalid-.com|RED|2"
  "mybrand.online|YELLOW|0"
  "mybrand.shop|YELLOW|0"
  "looks-fine.xyz|ORANGE|1"
)

run_case() {
  local domain="$1"
  local expected_band="$2"
  local expected_exit="$3"

  local out exit_code
  set +e
  out=$("$CLI" check --no-history --json -- "$domain" 2>/dev/null)
  exit_code=$?
  set -e

  local actual_band
  actual_band=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["verdict"]["band"])')

  if [[ "$actual_band" == "$expected_band" && "$exit_code" == "$expected_exit" ]]; then
    printf "  PASS  %-30s band=%-7s exit=%s\n" "$domain" "$actual_band" "$exit_code"
    PASS=$((PASS + 1))
  else
    printf "  FAIL  %-30s band=%-7s exit=%s (expected band=%s exit=%s)\n" \
      "$domain" "$actual_band" "$exit_code" "$expected_band" "$expected_exit"
    FAIL=$((FAIL + 1))
    FAILED_CASES+=("$domain")
  fi
}

echo "=== domain-pre-flight smoke tests ==="
echo "CLI: $CLI"
echo "Mode: $([[ $OFFLINE -eq 1 ]] && echo offline || echo full)"
echo

echo "[1/2] Offline structural + scoring cases"
for c in "${CASES[@]}"; do
  IFS='|' read -r domain band exit_code <<<"$c"
  run_case "$domain" "$band" "$exit_code"
done
echo

if [[ $OFFLINE -eq 0 ]]; then
  echo "[2/2] Wayback Machine integration check (network call)"
  if timeout 30 "$CLI" history example.com >/dev/null 2>&1; then
    echo "  PASS  Wayback lookup for example.com returned successfully"
    PASS=$((PASS + 1))
  else
    echo "  WARN  Wayback lookup failed or timed out — network/API issue, not a code regression"
    # Network flakiness is not a hard failure; just note it.
  fi
  echo
else
  echo "[2/2] Skipped (offline mode)"
  echo
fi

echo "=== Result: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  echo "Failed cases: ${FAILED_CASES[*]}" >&2
  exit 1
fi
exit 0
