from domain_pre_flight.checks.basic import check_basic
from domain_pre_flight.checks.history import HistoryReport
from domain_pre_flight.checks.score import aggregate


def _empty_history(domain: str) -> HistoryReport:
    return HistoryReport(
        domain=domain,
        has_archive=False,
        snapshot_count=0,
        first_seen=None,
        last_seen=None,
        age_days=None,
    )


def test_clean_com_is_green():
    basic = check_basic("example.com")
    v = aggregate(basic, _empty_history("example.com"))
    assert v.band == "GREEN"
    assert v.score >= 90


def test_high_risk_tld_drops_band():
    basic = check_basic("foobar.tk")
    v = aggregate(basic, _empty_history("foobar.tk"))
    assert v.band in {"ORANGE", "RED"}


def test_invalid_syntax_is_red():
    basic = check_basic("-invalid-.com")
    v = aggregate(basic, _empty_history("-invalid-.com"))
    assert v.band == "RED"


def test_hyphens_and_digits_lower_score():
    clean = aggregate(check_basic("nicebrand.com"), _empty_history("nicebrand.com"))
    spammy = aggregate(check_basic("buy-2024-cheap.com"), _empty_history("buy-2024-cheap.com"))
    assert spammy.score < clean.score
