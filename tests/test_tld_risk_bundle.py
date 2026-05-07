import json
from importlib.resources import files

from domain_pre_flight.checks.basic import TLD_RISK, _load_tld_risk, tld_risk_for


def test_tld_risk_loaded_from_json():
    path = files("domain_pre_flight.data") / "tld_risk.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["risk"]["tk"] == 70
    assert data["risk"]["com"] == 0
    assert "version" in data and "generated_at" in data
    assert "scale" in data


def test_tld_risk_table_matches_bundle():
    assert TLD_RISK["tk"] == 70
    assert TLD_RISK["com"] == 0
    assert TLD_RISK["xyz"] == 30


def test_tld_risk_for_unknown_returns_default():
    assert tld_risk_for("not-a-real-tld-xxx") == 25


def test_load_falls_back_when_corrupt(tmp_path, monkeypatch):
    # If the JSON file becomes invalid, the loader silently falls back to
    # the embedded dict. Simulate by pointing the loader at a missing
    # resource.
    from domain_pre_flight.checks import basic

    def boom(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(basic, "files", lambda *_a, **_kw: type("P", (), {"read_text": boom})())
    fresh = _load_tld_risk()
    # Falls back to the embedded baseline.
    assert fresh["com"] == 0
    assert fresh["tk"] == 70
