"""CLI-level tests via click's CliRunner.

Only offline checks are exercised: history is skipped with --no-history and
the network-dependent subcommands (rdap / dns / handles / trademark) are not
invoked here — their check functions have their own unit tests.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from domain_pre_flight.checks.score import EXIT_CODES, Band
from domain_pre_flight.cli import main

runner = CliRunner()


def _invoke(*args: str):
    return runner.invoke(main, list(args))


def test_no_subcommand_shows_help():
    result = _invoke()
    assert result.exit_code == 0
    assert "Pre-flight checks" in result.output


def test_basic_json():
    result = _invoke("basic", "example.com", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["domain"] == "example.com"
    assert payload["basic"]["sld"] == "example"
    assert payload["basic"]["length"] == len("example.com")
    assert payload["basic"]["is_valid_syntax"] is True


def test_basic_table_output():
    result = _invoke("basic", "example.com")
    assert result.exit_code == 0
    assert "Basic checks" in result.output
    assert "example" in result.output


def test_check_json_offline_sections_and_exit_code():
    result = _invoke("check", "example.com", "--json", "--no-history")
    payload = json.loads(result.output)
    # All sections are present as keys, skipped ones as null.
    for section in (
        "basic", "history", "handles", "typosquat", "trademark",
        "semantics", "llmo", "homograph", "rdap", "dns_sanity",
    ):
        assert section in payload
    assert payload["history"] is None  # --no-history
    assert payload["handles"] is None  # opt-in flag not given
    assert payload["typosquat"] is not None
    assert payload["llmo"] is not None
    band = Band(payload["verdict"]["band"])
    assert result.exit_code == EXIT_CODES[band]


def test_check_table_offline():
    result = _invoke("check", "example.com", "--no-history")
    assert "Basic checks" in result.output
    assert "score=" in result.output
    # Clean ASCII domain: the homograph section is suppressed by its predicate.
    assert "IDN homograph" not in result.output


def test_check_exit_code_matches_band_for_risky_name():
    # A brand-adjacent name should score worse than or equal to a clean one,
    # and the exit code must stay consistent with the reported band.
    result = _invoke("check", "g00gle.com", "--json", "--no-history")
    payload = json.loads(result.output)
    band = Band(payload["verdict"]["band"])
    assert result.exit_code == EXIT_CODES[band]
    assert payload["typosquat"]["matches"]


def test_llmo_json():
    result = _invoke("llmo", "example.com", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "llmo" in payload
    assert 0 <= payload["llmo"]["fitness"] <= 20


def test_semantics_json_with_languages_filter():
    result = _invoke("semantics", "example.com", "--languages", "en", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["domain"] == "example.com"
    assert "semantics" in payload


def test_typosquat_table():
    result = _invoke("typosquat", "example.com")
    assert result.exit_code == 0
    assert "Typosquat" in result.output


def test_permutations_json_with_limit_and_kind():
    result = _invoke("permutations", "example.com", "--limit", "5", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    perms = payload["permutations"]["permutations"]
    assert len(perms) <= 5

    result = _invoke("permutations", "example.com", "--kind", "omission", "--json")
    payload = json.loads(result.output)
    assert all(p["kind"] == "omission" for p in payload["permutations"]["permutations"])


def test_homograph_json_clean_domain():
    result = _invoke("homograph", "example.com", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["homograph"]["severity"] == "clean"
