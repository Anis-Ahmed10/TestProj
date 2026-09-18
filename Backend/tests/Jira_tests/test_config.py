import pytest

from app.core.config import Settings, get_settings


def test_normalize_log_level_valid():
    settings = Settings(log_level="debug")

    assert settings.log_level == "DEBUG"


def test_normalize_log_level_invalid():
    with pytest.raises(ValueError):
        Settings(log_level="invalid")


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()

    assert s1 is s2
