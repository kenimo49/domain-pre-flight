from domain_pre_flight.checks.trademark import check_trademark


def test_default_returns_three_deeplinks():
    r = check_trademark("nicebrand.com")
    assert {j.jurisdiction for j in r.jurisdictions} == {"us", "eu", "jp"}
    for j in r.jurisdictions:
        assert j.status == "not_supported"
        assert j.deeplink
        assert "nicebrand" in j.deeplink
        assert j.matches == []


def test_subset_jurisdictions():
    r = check_trademark("nicebrand.com", jurisdictions=["us"])
    assert len(r.jurisdictions) == 1
    assert r.jurisdictions[0].jurisdiction == "us"
    assert r.jurisdictions[0].deeplink.startswith("https://tmsearch.uspto.gov/")


def test_eu_deeplink_uses_tmview():
    r = check_trademark("nicebrand.com", jurisdictions=["eu"])
    assert r.jurisdictions[0].deeplink.startswith("https://www.tmdn.org/tmview/")


def test_jp_deeplink_uses_j_platpat():
    r = check_trademark("nicebrand.com", jurisdictions=["jp"])
    assert r.jurisdictions[0].deeplink.startswith("https://www.j-platpat.inpit.go.jp/")


def test_invalid_domain():
    r = check_trademark(".")
    assert r.jurisdictions == []
    assert any("no SLD" in n for n in r.notes)


def test_unknown_jurisdiction_noted():
    r = check_trademark("nicebrand.com", jurisdictions=["mars"])
    assert r.jurisdictions == []
    assert any("mars" in n for n in r.notes)


def test_has_exact_match_is_false_in_deeplink_only_mode():
    r = check_trademark("nicebrand.com")
    assert not r.has_exact_match


def test_top_level_note_steers_user_to_deeplinks():
    r = check_trademark("nicebrand.com")
    assert any("manually" in n.lower() for n in r.notes)


def test_deeplink_url_encodes_sld():
    from domain_pre_flight.checks.trademark import _deeplink_for

    j = _deeplink_for("us", "ace+co")
    assert "%2B" in j.deeplink and "ace+co" not in j.deeplink.split("?", 1)[1]
