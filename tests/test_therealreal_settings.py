"""Tests for The RealReal settings."""

from marketplace.therealreal_settings import TheRealRealSettings


def _settings(**overrides) -> TheRealRealSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="therealreal_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_reserved=False,
        include_final_sale=True,
        include_discounted_only=False,
    )
    defaults.update(overrides)
    return TheRealRealSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.include_final_sale is True
    assert s.default_currency == "JPY"


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(100) == 50


def test_max_pages_bounds() -> None:
    assert _settings().validate_max_pages(0) == 1


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.THEREALREAL_ENABLED", True)
    monkeypatch.setattr("config.settings.THEREALREAL_INCLUDE_FINAL_SALE", False)
    s = TheRealRealSettings.from_env()
    assert s.enabled is True
    assert s.include_final_sale is False
