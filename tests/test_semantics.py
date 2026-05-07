from domain_pre_flight.checks.semantics import check_semantics


def test_clean_name_no_match():
    r = check_semantics("nicebrand.com")
    assert r.matches == []
    assert r.issues == []


def test_severe_exact_english():
    r = check_semantics("fuck.com", languages=["en"])
    assert any(m.severity == "severe" and m.kind == "exact" for m in r.matches)
    assert any("severe" in i.lower() and "do not" in i.lower() for i in r.issues)


def test_severe_substring_portuguese():
    r = check_semantics("getputaway.com", languages=["pt"])
    assert any(m.term == "puta" and m.kind == "substring" and m.severity == "severe" for m in r.matches)
    assert any("severe" in i.lower() for i in r.issues)


def test_japanese_romaji_negative():
    r = check_semantics("shineyo.com", languages=["ja"])
    assert any(m.term == "shineyo" for m in r.matches)


def test_korean_romaji_negative():
    r = check_semantics("shibal.com", languages=["ko"])
    assert any(m.term == "shibal" for m in r.matches)


def test_chinese_pinyin_negative():
    r = check_semantics("shabicompany.com", languages=["zh"])
    assert any(m.term == "shabi" and m.severity == "severe" for m in r.matches)


def test_mild_substring_yields_note_not_issue():
    r = check_semantics("damnsmart.com", languages=["en"])
    mild = [m for m in r.matches if m.severity == "mild"]
    assert mild
    assert r.issues == []
    assert any("damn" in n for n in r.notes)


def test_invalid_domain():
    r = check_semantics(".")
    assert r.matches == []
    assert any("no SLD" in n for n in r.notes)


def test_unsupported_language_noted():
    r = check_semantics("nicebrand.com", languages=["xx"])
    assert any("xx" in n for n in r.notes)


def test_short_term_does_not_substring_match():
    # "sex" (length 3) is severe but should NOT substring-match "essex" or
    # "complex" — only exact matches qualify for terms shorter than 4 chars.
    r = check_semantics("essex.com", languages=["en"])
    assert all(m.kind == "exact" for m in r.matches if m.term == "sex")


def test_languages_default_covers_supported_set():
    r = check_semantics("nicebrand.com")
    assert set(r.languages) >= {"en", "es", "pt", "ja", "ko", "zh"}
