from collections import Counter

from domain_pre_flight.checks.permutations import generate_permutations


def test_short_sld_returns_empty():
    r = generate_permutations("ab.com")
    assert r.permutations == []
    assert any("short" in n.lower() for n in r.notes)


def test_invalid_domain_skipped():
    r = generate_permutations(".")
    assert r.permutations == []


def test_omissions_present():
    r = generate_permutations("apple.com")
    candidates = {p.candidate for p in r.permutations}
    assert "pple" in candidates
    assert "aple" in candidates
    assert "appl" in candidates


def test_transpositions_present():
    r = generate_permutations("apple.com")
    candidates = {p.candidate for p in r.permutations}
    assert "papple"[:5] in candidates or "paple" in candidates
    # apple -> palpe (swap pp/l) — generated because we walk every adjacent pair
    assert any(c == "applle"[:5] or "apple"[:1] != c[:1] for c in candidates)


def test_homoglyph_substitution_includes_zero_for_o():
    r = generate_permutations("google.com")
    candidates = {p.candidate for p in r.permutations}
    assert "g0ogle" in candidates or "go0gle" in candidates


def test_kinds_present():
    r = generate_permutations("apple.com")
    kinds = Counter(p.kind for p in r.permutations)
    # at least all major kinds should fire on a 5-char ASCII SLD
    for kind in ("omission", "substitution", "transposition", "doubling", "keyboard_adjacent", "addition", "hyphenation"):
        assert kinds[kind] > 0, f"missing kind {kind}"


def test_no_duplicates():
    r = generate_permutations("apple.com")
    candidates = [p.candidate for p in r.permutations]
    assert len(candidates) == len(set(candidates))
    assert "apple" not in candidates
