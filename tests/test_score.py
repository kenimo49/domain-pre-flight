from domain_pre_flight.checks.basic import check_basic
from domain_pre_flight.checks.history import HistoryReport
from domain_pre_flight.checks.score import Band, aggregate


def test_clean_com_is_green():
    v = aggregate(check_basic("example.com"), HistoryReport(domain="example.com"))
    assert v.band is Band.GREEN
    assert v.score >= 90


def test_high_risk_tld_drops_band():
    v = aggregate(check_basic("foobar.tk"), HistoryReport(domain="foobar.tk"))
    assert v.band in {Band.ORANGE, Band.RED}


def test_invalid_syntax_is_red():
    v = aggregate(check_basic("-invalid-.com"), HistoryReport(domain="-invalid-.com"))
    assert v.band is Band.RED


def test_hyphens_and_digits_lower_score():
    clean = aggregate(check_basic("nicebrand.com"), HistoryReport(domain="nicebrand.com"))
    spammy = aggregate(check_basic("buy-2024-cheap.com"), HistoryReport(domain="buy-2024-cheap.com"))
    assert spammy.score < clean.score


def test_band_values_are_strings():
    assert Band.GREEN == "GREEN"
    assert str(Band.GREEN.value) == "GREEN"
