from domain_pre_flight.checks.idn_homograph import check_idn_homograph


def test_pure_ascii_is_clean():
    r = check_idn_homograph("apple.com")
    assert r.is_idn is False
    assert r.has_confusables is False
    assert r.severity == "clean"
    assert r.issues == []


def test_invalid_domain_skipped():
    r = check_idn_homograph(".")
    assert r.severity == "clean"
    assert any("no SLD" in n for n in r.notes)


def test_cyrillic_google_homograph_brand_collision():
    # SLD with Cyrillic о (U+043E) substituted for Latin o → de-confuses to "google"
    spoof = "g" + "оо" + "gle"  # explicit Cyrillic small letter o (U+043E)
    r = check_idn_homograph(f"{spoof}.com", brands=["google"])
    assert r.is_idn is True
    assert r.has_confusables is True
    assert r.de_confused == "google"
    assert r.severity == "brand_collision"
    assert r.brand_collision == "google"
    assert any("phishing" in i.lower() for i in r.issues)


def test_idn_without_brand_collision_is_confusable_only():
    r = check_idn_homograph("аbcdef.com", brands=["apple", "github"])
    assert r.is_idn is True
    assert r.severity == "confusable"
    assert r.brand_collision == ""
    assert r.issues == []
    assert any("confusable" in n.lower() for n in r.notes)


def test_idn_present_but_not_brand_collision_is_confusable_only():
    # Realistic: an IDN that is_confusable returns findings for, but the
    # de-confused form is not in the brand list.
    r = check_idn_homograph("аbcdef.com", brands=["google", "apple"])
    assert r.is_idn is True
    assert r.severity == "confusable"
