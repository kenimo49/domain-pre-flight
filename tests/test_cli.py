"""CLI-level tests via click's CliRunner.

Offline checks run for real; the network-dependent checks (history / rdap /
dns / handles / trademark) are exercised through monkeypatched stub reports —
their check functions have their own unit tests.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from domain_pre_flight import cli
from domain_pre_flight.checks.dns_sanity import DnsSanityReport
from domain_pre_flight.checks.handles import HandleReport, HandleResult
from domain_pre_flight.checks.history import HistoryReport
from domain_pre_flight.checks.rdap import RdapReport
from domain_pre_flight.checks.score import EXIT_CODES, Band
from domain_pre_flight.checks.trademark import JurisdictionResult, TrademarkReport
from domain_pre_flight.cli import main

runner = CliRunner()


def _stub_network_checks(monkeypatch) -> None:
    """Replace every network-touching check with a deterministic stub report."""
    monkeypatch.setattr(
        cli,
        "check_history",
        lambda d: HistoryReport(domain=d, has_archive=True, snapshot_count=3, notes=["stub history note"]),
    )
    monkeypatch.setattr(
        cli,
        "check_handles",
        lambda d, platforms=None: HandleReport(
            domain=d,
            sld="example",
            results=[HandleResult(platform="github", status="taken")],
            notes=["stub handle note"],
        ),
    )
    monkeypatch.setattr(
        cli,
        "check_trademark",
        lambda d, jurisdictions=None: TrademarkReport(
            domain=d,
            sld="example",
            jurisdictions=[JurisdictionResult(jurisdiction="us", status="ok")],
            issues=["stub trademark issue"],
        ),
    )
    monkeypatch.setattr(
        cli,
        "check_rdap",
        lambda d: RdapReport(domain=d, registrar="Stub Registrar", issues=["stub rdap issue"]),
    )
    monkeypatch.setattr(
        cli,
        "check_dns_sanity",
        lambda d: DnsSanityReport(domain=d, mx="present", issues=["stub dns issue"]),
    )


def _invoke(*args: str):
    return runner.invoke(main, list(args))


def _flat(output: str) -> str:
    """Collapse whitespace: rich wraps table titles at the table width."""
    return " ".join(output.split())


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


def test_check_json_all_sections_locks_key_order(monkeypatch):
    """Full `check` run with every opt-in flag: locks the JSON contract.

    Guards the _payload refactor — key order and the null/non-null split must
    stay exactly as the pre-refactor implementation emitted them.
    """
    _stub_network_checks(monkeypatch)
    result = _invoke(
        "check", "example.com", "--json",
        "--check-handles", "--check-trademark", "--check-rdap", "--check-dns",
    )
    payload = json.loads(result.output)
    assert list(payload.keys()) == [
        "domain", "verdict", "basic", "history", "handles", "typosquat",
        "trademark", "semantics", "llmo", "homograph", "rdap", "dns_sanity",
    ]
    for section in ("history", "handles", "typosquat", "trademark",
                    "semantics", "llmo", "homograph", "rdap", "dns_sanity"):
        assert payload[section] is not None, section
    assert payload["handles"]["results"][0]["platform"] == "github"
    assert payload["rdap"]["registrar"] == "Stub Registrar"
    band = Band(payload["verdict"]["band"])
    assert result.exit_code == EXIT_CODES[band]


def test_check_table_renders_every_section(monkeypatch):
    """Full `check` table run: every _SECTIONS entry must render its table
    and its issue/note labels (guards attr/label/renderer mismatches)."""
    _stub_network_checks(monkeypatch)
    result = _invoke(
        "check", "example.com",
        "--check-handles", "--check-trademark", "--check-rdap", "--check-dns",
    )
    flat = _flat(result.output)
    for fragment in (
        "History (Wayback Machine)",
        "Handle availability for 'example'",
        "Typosquat / brand similarity",
        "Trademark search for 'example'",
        "Negative-meaning scan for 'example'",
        "LLMO fitness for 'example'",
        "RDAP for 'example.com'",
        "DNS hygiene for 'example.com'",
        "History notes:",
        "Handle notes:",
        "Trademark issues:",
        "RDAP issues:",
        "DNS issues:",
    ):
        assert fragment in flat, fragment
    # HandleReport has no `issues` attribute — the compat path must not
    # invent an issues block for it.
    assert "Handle issues:" not in flat
    # Clean ASCII domain: homograph stays suppressed even in the full run.
    assert "IDN homograph" not in flat


def test_handles_subcommand_stubbed(monkeypatch):
    _stub_network_checks(monkeypatch)
    result = _invoke("handles", "example.com")
    assert result.exit_code == 0
    assert "Handle availability for 'example'" in _flat(result.output)
    assert "Handle issues:" not in _flat(result.output)

    result = _invoke("handles", "example.com", "--json")
    payload = json.loads(result.output)
    assert payload["handles"]["results"][0]["status"] == "taken"


def test_rdap_subcommand_stubbed(monkeypatch):
    _stub_network_checks(monkeypatch)
    result = _invoke("rdap", "example.com")
    assert result.exit_code == 0
    assert "RDAP for 'example.com'" in _flat(result.output)
    assert "Issues:" in result.output

    result = _invoke("rdap", "example.com", "--json")
    assert json.loads(result.output)["rdap"]["issues"] == ["stub rdap issue"]


def test_dns_subcommand_stubbed(monkeypatch):
    _stub_network_checks(monkeypatch)
    result = _invoke("dns", "example.com")
    assert result.exit_code == 0
    assert "DNS hygiene for 'example.com'" in _flat(result.output)

    result = _invoke("dns", "example.com", "--json")
    assert json.loads(result.output)["dns_sanity"]["mx"] == "present"


def test_trademark_subcommand_stubbed(monkeypatch):
    _stub_network_checks(monkeypatch)
    result = _invoke("trademark", "example.com")
    assert result.exit_code == 0
    assert "Trademark search for 'example'" in _flat(result.output)
    assert "Issues:" in result.output

    result = _invoke("trademark", "example.com", "--json")
    assert json.loads(result.output)["trademark"]["jurisdictions"][0]["jurisdiction"] == "us"


def test_history_subcommand_stubbed(monkeypatch):
    _stub_network_checks(monkeypatch)
    result = _invoke("history", "example.com")
    assert result.exit_code == 0
    assert "archived=True" in result.output

    result = _invoke("history", "example.com", "--json")
    assert json.loads(result.output)["history"]["snapshot_count"] == 3
