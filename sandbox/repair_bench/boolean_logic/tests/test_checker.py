from boolean_logic.checker import can_access


def test_adult_with_permission():
    assert can_access(25, True) is True


def test_adult_without_permission():
    assert can_access(25, False) is False


def test_minor_with_permission():
    assert can_access(16, True) is False


def test_minor_without_permission():
    assert can_access(16, False) is False
