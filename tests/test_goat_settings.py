"""Tests for GOAT settings."""

from marketplace.goat_settings import GoatSettings


def _settings(**overrides) -> GoatSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="goat_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_new=True,
        include_used=True,
        require_known_price=True,
    )
    defaults.update(overrides)
    return GoatSettings(**defaults)


def test_defaults() -> None:
    settings = _settings()
    assert settings.default_currency == "JPY"
    assert settings.require_known_price is True


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(0) == 20
    assert _settings().validate_page_size(100) == 50


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.GOAT_ENABLED", True)
    monkeypatch.setattr("config.settings.GOAT_INCLUDE_USED", False)
    settings = GoatSettings.from_env()
    assert settings.enabled is True
    assert settings.include_used is False
