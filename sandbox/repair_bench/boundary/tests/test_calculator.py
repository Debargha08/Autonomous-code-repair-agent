from repair_bench.boundary.calculator import clamp


def test_value_inside_range():
    assert clamp(5, 0, 10) == 5


def test_value_below_minimum():
    assert clamp(-5, 0, 10) == 0


def test_value_above_maximum():
    assert clamp(15, 0, 10) == 10


def test_value_at_minimum():
    assert clamp(0, 0, 10) == 0


def test_value_at_maximum():
    assert clamp(10, 0, 10) == 10
