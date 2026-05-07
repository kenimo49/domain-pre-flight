import responses

from domain_pre_flight.checks.handles import (
    check_github,
    check_handles,
    check_instagram,
    check_npm,
    check_pypi,
    check_twitter,
)


@responses.activate
def test_github_taken():
    responses.add(responses.GET, "https://api.github.com/users/foo", status=200)
    r = check_github("foo")
    assert r.platform == "github"
    assert r.status == "taken"


@responses.activate
def test_github_available():
    responses.add(responses.GET, "https://api.github.com/users/zzznotreal", status=404)
    r = check_github("zzznotreal")
    assert r.status == "available"


@responses.activate
def test_github_rate_limited():
    responses.add(responses.GET, "https://api.github.com/users/foo", status=403)
    r = check_github("foo")
    assert r.status == "unknown"
    assert "rate" in r.detail.lower()


@responses.activate
def test_npm_taken():
    responses.add(responses.GET, "https://registry.npmjs.org/express", status=200)
    r = check_npm("express")
    assert r.status == "taken"


@responses.activate
def test_npm_available():
    responses.add(responses.GET, "https://registry.npmjs.org/zzz404pkg", status=404)
    r = check_npm("zzz404pkg")
    assert r.status == "available"


@responses.activate
def test_pypi_taken():
    responses.add(responses.GET, "https://pypi.org/pypi/requests/json", status=200)
    r = check_pypi("requests")
    assert r.status == "taken"


@responses.activate
def test_pypi_available():
    responses.add(responses.GET, "https://pypi.org/pypi/zzz404pkg/json", status=404)
    r = check_pypi("zzz404pkg")
    assert r.status == "available"


@responses.activate
def test_twitter_404_treated_as_available():
    responses.add(responses.HEAD, "https://twitter.com/freshname", status=404)
    r = check_twitter("freshname")
    assert r.status == "available"


@responses.activate
def test_twitter_200_returns_unknown_due_to_bot_protection():
    responses.add(responses.HEAD, "https://twitter.com/elonmusk", status=200)
    r = check_twitter("elonmusk")
    assert r.status == "unknown"
    assert "bot" in r.detail.lower()


@responses.activate
def test_instagram_404_available():
    responses.add(responses.HEAD, "https://www.instagram.com/freshname/", status=404)
    r = check_instagram("freshname")
    assert r.status == "available"


@responses.activate
def test_check_handles_full_fanout():
    responses.add(responses.GET, "https://api.github.com/users/example", status=200)
    responses.add(responses.GET, "https://registry.npmjs.org/example", status=404)
    responses.add(responses.GET, "https://pypi.org/pypi/example/json", status=200)
    responses.add(responses.HEAD, "https://twitter.com/example", status=404)
    responses.add(responses.HEAD, "https://www.instagram.com/example/", status=404)

    report = check_handles("example.com")

    assert report.sld == "example"
    statuses = {r.platform: r.status for r in report.results}
    assert statuses == {
        "github": "taken",
        "npm": "available",
        "pypi": "taken",
        "twitter": "available",
        "instagram": "available",
    }
    assert any("taken" in note for note in report.notes)


@responses.activate
def test_check_handles_subset():
    responses.add(responses.GET, "https://api.github.com/users/example", status=200)
    report = check_handles("example.com", platforms=["github"])
    assert len(report.results) == 1
    assert report.results[0].platform == "github"


def test_check_handles_unknown_platform_noted():
    report = check_handles("example.com", platforms=["telegram"])
    assert report.results == []
    assert any("telegram" in note for note in report.notes)


def test_check_handles_invalid_domain():
    report = check_handles(".")
    assert report.results == []
    assert any("no sld" in note.lower() for note in report.notes)


def test_check_handles_transport_error_returns_unknown(monkeypatch):
    import requests
    from domain_pre_flight.checks import handles as handles_mod

    def boom(*args, **kwargs):
        raise requests.ConnectionError("nope")

    monkeypatch.setattr(handles_mod.requests, "request", boom)
    r = check_github("example")
    assert r.status == "unknown"
    assert "transport" in r.detail.lower()
