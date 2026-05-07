from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver

from domain_pre_flight.checks.dns_sanity import check_dns_sanity


def _mock_answer(records: list[str], *, kind: str = "TXT"):
    """Build a fake dns.resolver answer iterable."""
    rrs = []
    for rec in records:
        rr = MagicMock()
        if kind == "TXT":
            rr.strings = [rec.encode("utf-8")]
        else:  # MX
            rr.exchange = MagicMock()
            rr.exchange.__str__ = lambda self, r=rec: r
        rrs.append(rr)
    answer = MagicMock()
    answer.__iter__ = lambda self: iter(rrs)
    return answer


def _resolve_factory(table: dict[tuple[str, str], object]):
    """Return a resolve(name, rdtype) implementation that pulls from a table."""
    def _resolve(name, rdtype):
        key = (str(name), rdtype)
        v = table.get(key)
        if v is None:
            raise dns.resolver.NoAnswer
        if isinstance(v, Exception):
            raise v
        return v

    return _resolve


def test_invalid_domain_skipped():
    r = check_dns_sanity(".")
    assert r.mx == "unknown"
    assert any("no SLD" in n for n in r.notes)


def test_clean_email_setup_no_issues():
    table = {
        ("example.com", "MX"): _mock_answer(["mx.example.com"], kind="MX"),
        ("example.com", "TXT"): _mock_answer(["v=spf1 include:_spf.example.com ~all"]),
        ("_dmarc.example.com", "TXT"): _mock_answer(["v=DMARC1; p=reject; rua=mailto:dmarc@example.com"]),
    }
    with patch("domain_pre_flight.checks.dns_sanity.dns.resolver.Resolver") as m:
        instance = MagicMock()
        instance.resolve.side_effect = _resolve_factory(table)
        m.return_value = instance
        r = check_dns_sanity("example.com")
    assert r.mx == "present"
    assert r.spf == "present"
    assert r.dmarc == "present"
    assert r.issues == []


def test_mx_without_spf_flags_issue():
    table = {
        ("example.com", "MX"): _mock_answer(["mx.example.com"], kind="MX"),
        ("example.com", "TXT"): _mock_answer(["some-other-txt"]),
        ("_dmarc.example.com", "TXT"): _mock_answer(["v=DMARC1; p=none"]),
    }
    with patch("domain_pre_flight.checks.dns_sanity.dns.resolver.Resolver") as m:
        instance = MagicMock()
        instance.resolve.side_effect = _resolve_factory(table)
        m.return_value = instance
        r = check_dns_sanity("example.com")
    assert r.mx == "present"
    assert r.spf == "absent"
    assert any("SPF" in i for i in r.issues)


def test_mx_without_dmarc_flags_issue():
    table = {
        ("example.com", "MX"): _mock_answer(["mx.example.com"], kind="MX"),
        ("example.com", "TXT"): _mock_answer(["v=spf1 ~all"]),
        # _dmarc.example.com is absent → NoAnswer
    }
    with patch("domain_pre_flight.checks.dns_sanity.dns.resolver.Resolver") as m:
        instance = MagicMock()
        instance.resolve.side_effect = _resolve_factory(table)
        m.return_value = instance
        r = check_dns_sanity("example.com")
    assert r.mx == "present"
    assert r.spf == "present"
    assert r.dmarc == "absent"
    assert any("DMARC" in i for i in r.issues)


def test_no_mx_at_all_is_note_not_issue():
    # All NXDOMAIN/absent
    table: dict = {}
    with patch("domain_pre_flight.checks.dns_sanity.dns.resolver.Resolver") as m:
        instance = MagicMock()
        instance.resolve.side_effect = _resolve_factory(table)
        m.return_value = instance
        r = check_dns_sanity("example.com")
    assert r.mx == "absent"
    assert r.issues == []
    assert any("MX" in n or "email" in n.lower() for n in r.notes)


def test_dns_timeout_yields_unknown():
    def boom(name, rdtype):
        raise dns.exception.Timeout

    with patch("domain_pre_flight.checks.dns_sanity.dns.resolver.Resolver") as m:
        instance = MagicMock()
        instance.resolve.side_effect = boom
        m.return_value = instance
        r = check_dns_sanity("example.com")
    assert r.mx == "unknown"
    assert r.spf == "unknown"
    assert r.dmarc == "unknown"
