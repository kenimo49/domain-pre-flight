from domain_pre_flight.checks.basic import check_basic, parse_domain


def test_parse_domain_simple():
    assert parse_domain("example.com") == ("example", "com")


def test_parse_domain_subdomain():
    assert parse_domain("foo.example.com") == ("example", "com")


def test_parse_domain_multi_label_tld():
    assert parse_domain("example.co.jp") == ("example", "co.jp")


def test_parse_domain_no_tld():
    assert parse_domain("localhost") == ("localhost", "")


def test_basic_clean_com():
    r = check_basic("example.com")
    assert r.is_valid_syntax
    assert r.tld == "com"
    assert r.sld == "example"
    assert r.hyphens == 0
    assert r.digits == 0
    assert not r.has_idn
    assert r.length == 11


def test_basic_high_risk_tld():
    r = check_basic("foo.xyz")
    assert r.tld == "xyz"
    assert any("xyz" in s for s in r.notes + r.issues)


def test_basic_hyphens_and_digits():
    r = check_basic("buy-cheap-2024-deals.com")
    assert r.hyphens == 3
    assert r.digits == 4
    assert any("hyphen" in i for i in r.issues)
    assert any("digit" in i for i in r.issues)


def test_basic_short_sld():
    r = check_basic("ab.com")
    assert any("short" in i.lower() for i in r.issues)


def test_basic_idn():
    r = check_basic("xn--exmpl-abc.com")
    assert r.has_idn
    assert any("idn" in n.lower() or "punycode" in n.lower() for n in r.notes)


def test_basic_invalid_syntax():
    r = check_basic("-invalid-.com")
    assert not r.is_valid_syntax
    assert any("invalid" in i.lower() for i in r.issues)
