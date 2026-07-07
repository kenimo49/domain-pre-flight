import pytest

pytest.importorskip("mcp")

from domain_pre_flight import mcp_server  # noqa: E402
from domain_pre_flight.checks.history import HistoryReport  # noqa: E402


@pytest.fixture(autouse=True)
def offline_history(monkeypatch):
    monkeypatch.setattr(
        mcp_server,
        "check_history",
        lambda domain: HistoryReport(domain=domain, notes=["stubbed for tests"]),
    )


def test_tools_are_registered():
    registered = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert registered == {
        "check_domain",
        "check_handles",
        "check_trademark",
        "list_typo_permutations",
    }


def test_check_domain_returns_verdict_payload():
    payload = mcp_server.check_domain("nicebrand.com")
    assert payload["domain"] == "nicebrand.com"
    assert payload["verdict"]["band"] in {"GREEN", "YELLOW", "ORANGE", "RED"}
    assert 0 <= payload["verdict"]["score"] <= 100
    assert payload["basic"]["is_valid_syntax"] is True
    # opt-in sections stay off by default
    assert payload["handles"] is None
    assert payload["trademark"] is None
    assert payload["rdap"] is None
    assert payload["dns_sanity"] is None
    # default-on sections are present
    assert payload["typosquat"] is not None
    assert payload["semantics"] is not None
    assert payload["llmo"] is not None


def test_check_domain_brand_collision_scores_worse():
    clean = mcp_server.check_domain("nicebrand.com")
    dirty = mcp_server.check_domain("goolge.com")
    assert dirty["verdict"]["score"] < clean["verdict"]["score"]


def test_list_typo_permutations_limit_and_kind():
    payload = mcp_server.list_typo_permutations("example.com", limit=5)
    assert payload["sld"] == "example"
    assert len(payload["permutations"]) <= 5
    assert payload["total"] >= len(payload["permutations"])
    kinds = {p["kind"] for p in payload["permutations"]}
    assert kinds

    only_kind = next(iter(kinds))
    filtered = mcp_server.list_typo_permutations("example.com", kind=only_kind, limit=5)
    assert {p["kind"] for p in filtered["permutations"]} == {only_kind}


def test_payload_is_json_serializable():
    import json

    payload = mcp_server.check_domain("nicebrand.com")
    assert json.loads(json.dumps(payload)) == payload
