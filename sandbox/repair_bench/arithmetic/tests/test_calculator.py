from repair_bench.arithmetic.calculator import calculate_total


def test_basic_total():
    assert calculate_total(100, 3) == 300


def test_single_item():
    assert calculate_total(50, 1) == 50


def test_zero_quantity():
    assert calculate_total(100, 0) == 0


def test_multiple_items():
    assert calculate_total(25, 4) == 100
