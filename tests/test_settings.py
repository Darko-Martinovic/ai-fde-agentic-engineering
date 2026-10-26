import settings


def test_a_setting_names_another(monkeypatch):
    monkeypatch.setenv("BACKEND_HOST", "10.0.0.5")
    monkeypatch.setenv("BACKEND_PORT", "9001")
    assert settings.setting("UNDERCOVER_API") == "http://10.0.0.5:9001"


def test_a_value_from_the_environment_is_filled_in(monkeypatch):
    """Node passes a template through unexpanded, as Playwright does."""
    monkeypatch.setenv("TEST_URL", "http://${BACKEND_HOST}:${TEST_PORT}")
    monkeypatch.setenv("TEST_PORT", "7000")
    assert settings.setting("TEST_URL") == "http://127.0.0.1:7000"


def test_an_override_can_name_a_default(monkeypatch):
    """As a line in .env naming a key only .env.defaults sets."""
    monkeypatch.setenv("UNDERCOVER_API", "http://${BACKEND_HOST}:9002")
    assert settings.setting("UNDERCOVER_API") == "http://127.0.0.1:9002"


def test_an_optional_setting_left_out_or_empty_is_none(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert settings.optional_setting("DATABASE_URL") is None
    monkeypatch.setenv("DATABASE_URL", "")
    assert settings.optional_setting("DATABASE_URL") is None
    monkeypatch.setenv("DATABASE_URL", "postgresql://${BACKEND_HOST}/x")
    assert settings.optional_setting("DATABASE_URL") == "postgresql://127.0.0.1/x"
