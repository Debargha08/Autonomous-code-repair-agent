from repair_bench.retry_test.scorer import normalize_score


def test_negative_score():
    assert normalize_score(-10) == 0


def test_normal_score():
    assert normalize_score(50) == 50


def test_upper_boundary():
    assert normalize_score(100) == 100


def test_above_upper_boundary():
    assert normalize_score(150) == 100
