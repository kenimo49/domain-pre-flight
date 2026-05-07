# Recipe: Adding a platform to the handle check

You want `dpf handles example.com` to also report whether the matching name is taken on, say, GitLab or Hashnode. This is a one-module change that takes ~15 minutes if you follow the pattern.

## When to use this recipe

- The platform exposes a public endpoint that distinguishes "exists" from "does not exist" via HTTP status code (200 vs 404).
- The platform does not require auth for that distinction.
- The platform's bot protection is *not* aggressive enough to make all responses 200/302/403. If it is, `unknown` is the only honest answer for most domains, and adding the platform just adds noise.

If those conditions hold, do this:

## Steps

### 1. Add a checker in `checks/handles.py`

```python
def check_gitlab(name: str, timeout: int = DEFAULT_TIMEOUT) -> HandleResult:
    resp = _request("GET", f"https://gitlab.com/api/v4/users?username={name}", timeout)
    if resp is None:
        return HandleResult("gitlab", "unknown", "transport error")
    if resp.status_code == 200:
        # GitLab returns [] for not-taken names — distinguish from a hit
        try:
            data = resp.json()
            if data and isinstance(data, list):
                return HandleResult("gitlab", "taken")
            return HandleResult("gitlab", "available")
        except ValueError:
            return HandleResult("gitlab", "unknown", "non-JSON response")
    if resp.status_code == 404:
        return HandleResult("gitlab", "available")
    if resp.status_code == 429:
        return HandleResult("gitlab", "unknown", "rate-limited")
    return HandleResult("gitlab", "unknown", f"http {resp.status_code}")
```

Notes:

- Always go through `_request(...)` so the User-Agent and timeout handling are consistent.
- Any HTTP code that you cannot map confidently to taken/available is `unknown` with a `detail` string, never `available`.
- If the platform returns a 200 for *both* taken and not-taken with a body distinction (like GitLab's empty list), parse for the distinction and fall back to `unknown` if parsing fails.

### 2. Register the platform

```python
PLATFORM_CHECKS: dict[str, Callable[[str, int], HandleResult]] = {
    "github": check_github,
    "gitlab": check_gitlab,         # add this
    "npm": check_npm,
    "pypi": check_pypi,
    "twitter": check_twitter,
    "instagram": check_instagram,
}
```

### 3. Tests in `tests/test_handles.py`

Copy the existing GitHub test pattern:

```python
@responses.activate
def test_gitlab_taken():
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/users?username=foo",
        json=[{"id": 1, "username": "foo"}],
        status=200,
        match_querystring=True,
    )
    r = check_gitlab("foo")
    assert r.status == "taken"


@responses.activate
def test_gitlab_available():
    responses.add(
        responses.GET,
        "https://gitlab.com/api/v4/users?username=zzznotreal",
        json=[],
        status=200,
        match_querystring=True,
    )
    r = check_gitlab("zzznotreal")
    assert r.status == "available"


@responses.activate
def test_gitlab_rate_limited():
    responses.add(responses.GET, "https://gitlab.com/api/v4/users?username=foo", status=429, match_querystring=True)
    r = check_gitlab("foo")
    assert r.status == "unknown"
    assert "rate-limited" in r.detail
```

### 4. Update the help text

In `cli.py`, the `--platforms` help string lists the default platforms. Update it to include the new one.

```python
help="Comma-separated subset of platforms (default: github,gitlab,npm,pypi,twitter,instagram).",
```

Update the same wording in `README.md` and `docs/guide/usage.md`.

### 5. Validate

```bash
pytest -q tests/test_handles.py
.venv/bin/dpf handles example.com --platforms gitlab --json
```

The smoke test does not need a new case unless the new platform is essential — it tests CLI plumbing, not specific platform responses.

## Anti-patterns

- **Adding TikTok / Discord / Telegram.** They wall non-auth requests aggressively; the result is `unknown` for almost every name. Do not add platforms whose default response is `unknown`.
- **Faking success on rate-limit.** Tempting because tests pass; result is users registering names that are actually taken. Always return `unknown` on 429/403.
- **Hard-coding the User-Agent.** Use the module-level `USER_AGENT` constant.
