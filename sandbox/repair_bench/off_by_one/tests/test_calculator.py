from off_by_one.calculator import sum_range


def test_sum_all_values():
    assert sum_range([1, 2, 3, 4]) == 10


def test_single_value():
    assert sum_range([7]) == 7


def test_two_values():
    assert sum_range([5, 8]) == 13
