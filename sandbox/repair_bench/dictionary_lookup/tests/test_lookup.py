from dictionary_lookup.lookup import get_score


def test_existing_user():
    assert get_score({"alice": 80, "bob": 90}, "alice") == 80


def test_second_existing_user():
    assert get_score({"alice": 80, "bob": 90}, "bob") == 90


def test_missing_user():
    assert get_score({"alice": 80}, "charlie") == 0


def test_empty_scores():
    assert get_score({}, "charlie") == 0
