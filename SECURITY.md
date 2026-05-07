# Security policy

## Supported versions

The latest minor (`0.x`) is supported. Older releases receive no fixes.

## Reporting a vulnerability

`domain-pre-flight` is a defensive / pre-flight tool; it does not handle credentials, run servers, or process untrusted input at scale. The realistic vulnerability surfaces are:

1. The HTTP clients in `handles.py` / `rdap.py` (a malicious response could trigger excessive memory / CPU).
2. The DNS client in `dns_sanity.py` (a malicious authoritative server could attempt DoS via large TXT records).
3. The data-loading paths for `data/known_brands.txt` and `data/negative_meanings/*.txt` (a tampered repo could ship a poisoned word list).

To report a suspected vulnerability:

- Open a **private security advisory** at https://github.com/kenimo49/domain-pre-flight/security/advisories/new.
- Or email the maintainer directly (contact via the GitHub profile).

Please do **not** file a public issue for a suspected vulnerability.

## What to expect

- Acknowledgement within 5 working days.
- A patch or detailed mitigation guidance within 30 days for confirmed issues.
- Public disclosure only after the fix is released; CVE assignment if applicable.
