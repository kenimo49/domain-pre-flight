from domain_pre_flight.checks.llmo import check_llmo


def test_clean_short_name_is_excellent():
    r = check_llmo("apple.com")
    assert r.band in {"excellent", "good"}
    assert r.fitness >= 11
    assert r.issues == []


def test_long_consonant_cluster_penalised():
    r = check_llmo("strngths.com")
    assert r.cluster_score <= 1
    assert any("consonant cluster" in n for n in r.notes)


def test_low_vowel_ratio_penalised():
    r = check_llmo("pqrstv.com")
    assert r.vowel_score <= 1
    assert any("vowel" in n.lower() for n in r.notes)


def test_excessive_length_penalised():
    r = check_llmo("supercalifragilisticexpialidocious.com")
    assert r.length_score <= 1
    assert any("length" in n for n in r.notes)


def test_repeated_chars_penalised():
    r = check_llmo("zzzzbrand.com")
    assert r.repeats_score <= 2


def test_invalid_domain():
    r = check_llmo(".")
    assert r.fitness == 0
    assert r.band == "poor"
    assert any("no SLD" in n for n in r.notes)


def test_band_thresholds():
    r = check_llmo("apple.com")
    assert r.band == "excellent" or r.band == "good"

    r2 = check_llmo("xkqzpfvgthjs.com")
    assert r2.band in {"poor", "ok"}


def test_fitness_is_sum_of_axes():
    r = check_llmo("brand.com")
    assert r.fitness == r.cluster_score + r.vowel_score + r.length_score + r.repeats_score


def test_two_char_sld_low_length_score():
    r = check_llmo("ab.com")
    assert r.length_score <= 1


def test_clean_no_repeats_sld():
    r = check_llmo("brand.com")
    assert r.length_score == 5
    assert r.repeats_score == 5
