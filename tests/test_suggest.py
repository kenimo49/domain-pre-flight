"""Tests for domain_pre_flight.checks.suggest."""

from unittest.mock import MagicMock, patch

import pytest
import responses

from domain_pre_flight.checks.suggest import (
    SuggestCandidate,
    _hn_mentions,
    _rdap_available,
    _signal,
    check_suggest,
)

# ---------------------------------------------------------------------------
# _rdap_available
# ---------------------------------------------------------------------------


@responses.activate
def test_rdap_available_404_means_free():
    responses.add(responses.GET, "https://rdap.org/domain/newterm.com", status=404)
    assert _rdap_available("newterm.com") is True


@responses.activate
def test_rdap_available_200_means_taken():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/google.com",
        json={"ldhName": "google.com"},
        status=200,
    )
    assert _rdap_available("google.com") is False


@responses.activate
def test_rdap_available_403_is_inconclusive():
    responses.add(responses.GET, "https://rdap.org/domain/mystery.com", status=403)
    assert _rdap_available("mystery.com") is None


@responses.activate
def test_rdap_available_timeout_is_inconclusive():
    responses.add(
        responses.GET,
        "https://rdap.org/domain/slow.com",
        body=Exception("connection timeout"),
    )
    assert _rdap_available("slow.com") is None


# ---------------------------------------------------------------------------
# _hn_mentions
# ---------------------------------------------------------------------------


@responses.activate
def test_hn_mentions_returns_count():
    responses.add(
        responses.GET,
        "https://hn.algolia.com/api/v1/search",
        json={"nbHits": 42},
        status=200,
    )
    assert _hn_mentions("someterm") == 42


@responses.activate
def test_hn_mentions_returns_zero_on_api_error():
    responses.add(
        responses.GET,
        "https://hn.algolia.com/api/v1/search",
        status=500,
    )
    assert _hn_mentions("someterm") == 0


@responses.activate
def test_hn_mentions_returns_zero_on_network_error():
    responses.add(
        responses.GET,
        "https://hn.algolia.com/api/v1/search",
        body=Exception("network error"),
    )
    assert _hn_mentions("someterm") == 0


# ---------------------------------------------------------------------------
# _signal
# ---------------------------------------------------------------------------


def test_signal_green():
    assert _signal(10) == "🟢"
    assert _signal(100) == "🟢"


def test_signal_yellow():
    assert _signal(3) == "🟡"
    assert _signal(9) == "🟡"


def test_signal_grey():
    assert _signal(0) == "⚪"
    assert _signal(2) == "⚪"


# ---------------------------------------------------------------------------
# check_suggest — missing ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------


def test_check_suggest_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = check_suggest("example.com")
    assert report.candidates == []
    assert any("ANTHROPIC_API_KEY" in issue for issue in report.issues)


# ---------------------------------------------------------------------------
# check_suggest — anthropic package not installed
# ---------------------------------------------------------------------------


def test_check_suggest_no_anthropic_package(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch("domain_pre_flight.checks.suggest._generate_terms") as mock_gen:
        mock_gen.side_effect = ImportError("anthropic package not installed")
        report = check_suggest("example.com")
    assert report.candidates == []
    assert any("anthropic" in issue.lower() for issue in report.issues)


# ---------------------------------------------------------------------------
# check_suggest — happy path
# ---------------------------------------------------------------------------


def _make_anthropic_mock(terms: list[str]) -> MagicMock:
    """Build a minimal anthropic client mock that returns *terms* as text."""
    content_block = MagicMock()
    content_block.text = "\n".join(terms)
    message = MagicMock()
    message.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


@responses.activate
def test_check_suggest_happy_path(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    # RDAP: first term free, second taken
    responses.add(responses.GET, "https://rdap.org/domain/memorynet.com", status=404)
    responses.add(
        responses.GET,
        "https://rdap.org/domain/contextdb.com",
        json={"ldhName": "contextdb.com"},
        status=200,
    )
    # HN only called for the free one
    responses.add(
        responses.GET,
        "https://hn.algolia.com/api/v1/search",
        json={"nbHits": 7},
        status=200,
    )

    anthropic_mock = _make_anthropic_mock(["memorynet", "contextdb"])

    with patch("domain_pre_flight.checks.suggest._generate_terms", return_value=["memorynet", "contextdb"]):
        report = check_suggest("synthetmemory.com", count=2)

    assert report.issues == []
    assert len(report.candidates) == 2

    free = report.candidates[0]
    assert free.term == "memorynet"
    assert free.domain == "memorynet.com"
    assert free.available is True
    assert free.hn_mentions_30d == 7
    assert free.signal == "🟡"

    taken = report.candidates[1]
    assert taken.term == "contextdb"
    assert taken.available is False
    assert taken.hn_mentions_30d == 0
    assert taken.signal == ""


@responses.activate
def test_check_suggest_all_taken_adds_note(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    responses.add(
        responses.GET,
        "https://rdap.org/domain/amazon.com",
        json={"ldhName": "amazon.com"},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://rdap.org/domain/google.com",
        json={"ldhName": "google.com"},
        status=200,
    )

    with patch("domain_pre_flight.checks.suggest._generate_terms", return_value=["amazon", "google"]):
        report = check_suggest("bigcorp.com", count=2)

    assert any("already registered" in n for n in report.notes)


# ---------------------------------------------------------------------------
# check_suggest — invalid domain / no SLD
# ---------------------------------------------------------------------------


def test_check_suggest_no_sld(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    # TLD-only input produces empty SLD
    report = check_suggest(".com")
    assert report.candidates == []
    assert any("SLD" in issue or "skipped" in issue for issue in report.issues)


# ---------------------------------------------------------------------------
# check_suggest — RDAP inconclusive (unknown)
# ---------------------------------------------------------------------------


@responses.activate
def test_check_suggest_rdap_inconclusive(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    responses.add(responses.GET, "https://rdap.org/domain/unknownterm.com", status=403)

    with patch("domain_pre_flight.checks.suggest._generate_terms", return_value=["unknownterm"]):
        report = check_suggest("example.com", count=1)

    assert len(report.candidates) == 1
    assert report.candidates[0].available is None
    assert report.candidates[0].hn_mentions_30d == 0
