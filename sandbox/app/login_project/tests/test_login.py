from app.login_project.login import login


def test_valid_admin_login():
    assert login("admin", "password123") is True


def test_valid_debargha_login():
    assert login("debargha", "qwen123") is True


def test_wrong_password():
    assert login("admin", "wrongpassword") is False


def test_unknown_user():
    assert login("unknown", "password123") is False
