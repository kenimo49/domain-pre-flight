import responses

from domain_pre_flight.checks.rdap import check_rdap


@responses.activate
def test_rdap_ok_with_full_metadata():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/example.com",
        json={
            "ldhName": "example.com",
            "events": [
                {"eventAction": "registration", "eventDate": "1992-01-01T00:00:00+00:00"},
                {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00+00:00"},
                {"eventAction": "last changed", "eventDate": "2024-01-01T00:00:00+00:00"},
            ],
            "status": ["active"],
            "entities": [
                {
                    "roles": ["registrar"],
                    "handle": "292",
                    "vcardArray": [
                        "vcard",
                        [["fn", {}, "text", "MarkMonitor Inc."]],
                    ],
                },
            ],
        },
        status=200,
    )

    r = check_rdap("example.com")
    assert r.status == "ok"
    assert r.created_at and r.created_at.startswith("1992")
    assert r.expires_at and r.expires_at.startswith("2030")
    assert r.registrar == "MarkMonitor Inc."
    assert r.domain_status == ["active"]
    assert r.issues == []


@responses.activate
def test_rdap_404_means_not_registered():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/totally-not-real-fresh-name.com",
        status=404,
    )
    r = check_rdap("totally-not-real-fresh-name.com")
    assert r.status == "not_found"
    assert any("available" in n.lower() for n in r.notes)


@responses.activate
def test_rdap_5xx_is_lookup_failed():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/example.com",
        json={},
        status=503,
    )
    r = check_rdap("example.com")
    assert r.status == "lookup_failed"
    assert "503" in r.detail


@responses.activate
def test_rdap_risky_status_surfaces_issue():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/example.com",
        json={
            "events": [],
            "status": ["clientHold", "serverDeleteProhibited"],
            "entities": [],
        },
        status=200,
    )
    r = check_rdap("example.com")
    assert r.status == "ok"
    assert any("clientHold" in i for i in r.issues)


@responses.activate
def test_rdap_invalid_json_is_lookup_failed():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/example.com",
        body="not json",
        status=200,
        content_type="text/plain",
    )
    r = check_rdap("example.com")
    assert r.status == "lookup_failed"
    assert "non-JSON" in r.detail or "json" in r.detail.lower()


def test_rdap_invalid_domain_skipped():
    r = check_rdap(".")
    assert r.status == "lookup_failed"
    assert any("no SLD" in n for n in r.notes)


@responses.activate
def test_rdap_transport_error(monkeypatch):
    import requests

    from domain_pre_flight.checks import rdap as rdap_mod

    def boom(*args, **kwargs):
        raise requests.ConnectionError("nope")

    monkeypatch.setattr(rdap_mod.requests, "get", boom)
    r = check_rdap("example.com")
    assert r.status == "lookup_failed"
    assert "transport" in r.detail.lower()
