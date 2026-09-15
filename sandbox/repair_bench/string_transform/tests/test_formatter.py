from repair_bench.string_transform.formatter import normalize_username


def test_username_with_spaces():
    assert normalize_username("  Alice  ") == "alice"


def test_uppercase_username():
    assert normalize_username("BOB") == "bob"


def test_leading_spaces():
    assert normalize_username("  Charlie") == "charlie"


def test_trailing_spaces():
    assert normalize_username("David  ") == "david"


def test_already_normalized():
    assert normalize_username("eve") == "eve"
