from list_filter.filter import filter_positive


def test_positive_values():
    assert filter_positive([1, -2, 3, -4]) == [1, 3]


def test_all_positive():
    assert filter_positive([1, 2, 3]) == [1, 2, 3]


def test_all_negative():
    assert filter_positive([-1, -2, -3]) == []


def test_empty_list():
    assert filter_positive([]) == []
