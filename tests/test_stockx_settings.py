"""Tests for StockX settings."""

from marketplace.stockx_settings import StockXSettings


def _settings(**overrides) -> StockXSettings:
    defaults = dict(
        enabled=False,
        timeout_seconds=10,
        page_size=20,
        max_pages=1,
        default_currency="JPY",
        demo_fixture_path="stockx_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_inactive=False,
        include_new=True,
        include_preowned=False,
        include_low_liquidity=True,
        require_known_lowest_ask=True,
        require_known_shipping=False,
        require_known_fees=False,
        minimum_sales_last_30_days=0,
        minimum_asks_count=0,
        minimum_bids_count=0,
        maximum_volatility_rate=None,
        preferred_price_source="LOWEST_ASK",
    )
    defaults.update(overrides)
    return StockXSettings(**defaults)


def test_defaults() -> None:
    s = _settings()
    assert s.preferred_price_source == "LOWEST_ASK"
    assert s.require_known_lowest_ask is True


def test_page_size_bounds() -> None:
    assert _settings().validate_page_size(0) == 20


def test_price_source_normalization() -> None:
    assert StockXSettings.normalize_price_source("last_sale") == "LAST_SALE"
    assert StockXSettings.normalize_price_source("invalid") == "LOWEST_ASK"


def test_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.STOCKX_ENABLED", True)
    monkeypatch.setattr("config.settings.STOCKX_PREFERRED_PRICE_SOURCE", "NONE")
    s = StockXSettings.from_env()
    assert s.enabled is True
    assert s.preferred_price_source == "NONE"
