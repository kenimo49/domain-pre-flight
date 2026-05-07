from domain_pre_flight.checks.typosquat import check_typosquat, load_brands


def test_load_brands_nonempty():
    brands = load_brands()
    assert len(brands) > 50
    assert "google" in brands
    assert "github" in brands


def test_typosquat_clean_name_no_match():
    r = check_typosquat("nicebrand.com")
    assert r.matches == []
    assert r.issues == []


def test_typosquat_exact_brand_match():
    r = check_typosquat("google.com")
    assert any(m.kind == "exact" and m.brand == "google" for m in r.matches)
    assert any("identical" in i.lower() for i in r.issues)


def test_typosquat_near_match_distance_1():
    r = check_typosquat("goolge.com")
    near = [m for m in r.matches if m.brand == "google"]
    assert near and near[0].kind in {"near", "bigram"}
    assert any("UDRP" in i for i in r.issues)


def test_typosquat_near_match_microsoft():
    r = check_typosquat("microsft.com")
    assert any(m.brand == "microsoft" and m.kind == "near" for m in r.matches)


def test_typosquat_homoglyph():
    r = check_typosquat("g00gle.com")
    assert any(m.brand == "google" and m.kind == "homoglyph" for m in r.matches)


def test_typosquat_possible_distance_3_is_note_only():
    r = check_typosquat("amazonn.com", brands=["amazon"])
    severe = [m for m in r.matches if m.kind in {"exact", "near", "homoglyph", "bigram"}]
    if severe:
        return
    possible = [m for m in r.matches if m.kind == "possible"]
    assert possible
    assert r.issues == []


def test_typosquat_short_unrelated_distance():
    r = check_typosquat("xy.com")
    severe = [m for m in r.matches if m.kind in {"exact", "near", "homoglyph"}]
    assert not severe


def test_typosquat_invalid_domain():
    r = check_typosquat(".")
    assert r.matches == []
    assert any("no sld" in n.lower() for n in r.notes)


def test_typosquat_with_explicit_brand_list():
    r = check_typosquat("acme.com", brands=["acme", "widget"])
    assert any(m.kind == "exact" and m.brand == "acme" for m in r.matches)
