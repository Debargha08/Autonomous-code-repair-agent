from multiple_branches.classifier import classify_score


def test_grade_a():
    assert classify_score(95) == "A"


def test_grade_b():
    assert classify_score(80) == "B"


def test_grade_c():
    assert classify_score(65) == "C"


def test_grade_f():
    assert classify_score(40) == "F"
