import responses

from domain_pre_flight.checks.trademark import check_trademark


@responses.activate
def test_trademark_no_results_clean():
    responses.add(
        responses.GET,
        "https://tmsearch.uspto.gov/api/search/case",
        json={"hits": {"hits": []}},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://www.tmdn.org/tmview/api/search/results",
        json={"tradeMarks": []},
        status=200,
    )

    r = check_trademark("nicebrand.com", jurisdictions=["us", "eu"])
    by_j = {j.jurisdiction: j for j in r.jurisdictions}
    assert by_j["us"].status == "ok" and by_j["us"].matches == []
    assert by_j["eu"].status == "ok" and by_j["eu"].matches == []
    assert r.issues == []


@responses.activate
def test_trademark_exact_match_us():
    responses.add(
        responses.GET,
        "https://tmsearch.uspto.gov/api/search/case",
        json={
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "markIdentification": "Nicebrand",
                            "ownerName": "Acme Corp",
                            "statusDesc": "LIVE",
                            "serialNumber": "12345678",
                            "internationalClass": ["009"],
                        }
                    }
                ]
            }
        },
        status=200,
    )
    r = check_trademark("nicebrand.com", jurisdictions=["us"])
    us = r.jurisdictions[0]
    assert us.status == "ok"
    assert len(us.matches) == 1
    assert us.matches[0].similarity == "exact"
    assert us.matches[0].owner == "Acme Corp"
    assert r.has_exact_match
    assert any("UDRP" in i for i in r.issues)


@responses.activate
def test_trademark_similar_only_eu():
    responses.add(
        responses.POST,
        "https://www.tmdn.org/tmview/api/search/results",
        json={
            "tradeMarks": [
                {
                    "tmName": "NicebrandPlus",
                    "applicantName": "Foo Ltd",
                    "status": "Registered",
                    "applicationNumber": "EU000123",
                    "niceClass": [9, 42],
                }
            ]
        },
        status=200,
    )
    r = check_trademark("nicebrand.com", jurisdictions=["eu"])
    eu = r.jurisdictions[0]
    assert eu.matches[0].similarity == "similar"
    assert not r.has_exact_match
    assert any("similar marks" in n for n in r.notes)


@responses.activate
def test_trademark_uspto_lookup_failure():
    # Session retries on 502/503/504; provide enough mocked responses to
    # exhaust the retry budget, then assert the final lookup_failed state.
    for _ in range(4):
        responses.add(
            responses.GET,
            "https://tmsearch.uspto.gov/api/search/case",
            json={"error": "broken"},
            status=503,
        )
    r = check_trademark("nicebrand.com", jurisdictions=["us"])
    us = r.jurisdictions[0]
    assert us.status == "lookup_failed"
    assert any("could not query" in n for n in r.notes)


@responses.activate
def test_trademark_eu_lookup_failure():
    responses.add(
        responses.POST,
        "https://www.tmdn.org/tmview/api/search/results",
        json={"err": "timeout"},
        status=502,
    )
    r = check_trademark("nicebrand.com", jurisdictions=["eu"])
    eu = r.jurisdictions[0]
    assert eu.status == "lookup_failed"


def test_trademark_jp_returns_not_supported_with_deeplink():
    r = check_trademark("nicebrand.com", jurisdictions=["jp"])
    jp = r.jurisdictions[0]
    assert jp.status == "not_supported"
    assert jp.deeplink.startswith("https://www.j-platpat.inpit.go.jp/")
    assert "nicebrand" in jp.deeplink


def test_trademark_invalid_domain():
    r = check_trademark(".")
    assert r.jurisdictions == []
    assert any("no SLD" in n for n in r.notes)


def test_trademark_unknown_jurisdiction_noted():
    r = check_trademark("nicebrand.com", jurisdictions=["mars"])
    assert r.jurisdictions == []
    assert any("mars" in n for n in r.notes)


@responses.activate
def test_trademark_uspto_unrecognised_response_shape():
    responses.add(
        responses.GET,
        "https://tmsearch.uspto.gov/api/search/case",
        body="not json at all",
        status=200,
        content_type="text/plain",
    )
    r = check_trademark("nicebrand.com", jurisdictions=["us"])
    us = r.jurisdictions[0]
    assert us.status == "lookup_failed"
    assert "unrecognised" in us.detail or "transport" in us.detail or "json" in us.detail.lower()
