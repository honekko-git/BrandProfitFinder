"""Tests for Farfetch settings."""

from marketplace.farfetch_settings import FarfetchSettings


def _settings(**overrides) -> FarfetchSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="farfetch_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_reserved=False,
        include_discounted_only=False,
        include_full_price_only=False,
        include_low_stock=True,
        include_final_sale=False,
        include_partner_boutiques=True,
        include_platform_inventory=True,
        require_known_shipping=False,
        require_known_duties=False,
    )
    defaults.update(overrides)
    return FarfetchSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.include_low_stock is True
    assert s.include_partner_boutiques is True


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(0) == 20
    assert _settings().validate_max_pages(0) == 1


def test_effective_price_filters_conflict() -> None:
    discounted, full_price, warnings = _settings(
        include_discounted_only=True,
        include_full_price_only=True,
    ).effective_price_filters()
    assert discounted is True
    assert full_price is False
    assert warnings


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.FARFETCH_ENABLED", True)
    monkeypatch.setattr("config.settings.FARFETCH_REQUIRE_KNOWN_DUTIES", True)
    s = FarfetchSettings.from_env()
    assert s.enabled is True
    assert s.require_known_duties is True


def test_currency_uppercase(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.FARFETCH_DEFAULT_CURRENCY", "jpy")
    assert FarfetchSettings.from_env().default_currency == "JPY"
