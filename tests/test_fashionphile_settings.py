"""Tests for Fashionphile settings."""

from marketplace.fashionphile_settings import FashionphileSettings


def _settings(**overrides) -> FashionphileSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="fashionphile_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_reserved=False,
        include_discounted_only=False,
    )
    defaults.update(overrides)
    return FashionphileSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.page_size == 20
    assert s.default_currency == "JPY"
    assert s.include_discounted_only is False


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(1) == 1
    assert _settings().validate_page_size(100) == 50
    assert _settings(page_size=0).validate_page_size(None) >= 1


def test_max_pages_bounds() -> None:
    assert _settings().validate_max_pages(0) == 1
    assert _settings().validate_max_pages(100) == 20


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.FASHIONPHILE_ENABLED", True)
    monkeypatch.setattr("config.settings.FASHIONPHILE_PAGE_SIZE", 15)
    monkeypatch.setattr("config.settings.FASHIONPHILE_INCLUDE_RESERVED", True)
    s = FashionphileSettings.from_env()
    assert s.enabled is True
    assert s.page_size == 15
    assert s.include_reserved is True
