"""Tests for real profit verification models and configuration."""

from __future__ import annotations

from profit_discovery.discovery_validation.real_profit_config import (
    fashionphile_endpoint_status,
    resolve_usd_jpy_exchange_rate,
    yahoo_auction_endpoint_status,
)
from profit_discovery.discovery_validation.real_profit_models import (
    REAL_ROUTE_BRANDS,
    DataStatus,
)
from profit_discovery.discovery_validation.real_profit_verification import is_real_route_brand


def test_real_route_brands_are_limited() -> None:
    assert REAL_ROUTE_BRANDS == ("Chanel", "Louis Vuitton")
    assert is_real_route_brand("Chanel")
    assert is_real_route_brand("Louis Vuitton")
    assert not is_real_route_brand("Hermes")


def test_exchange_rate_uses_default_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("USD_JPY_EXCHANGE_RATE", raising=False)
    assert resolve_usd_jpy_exchange_rate() == 160.0


def test_exchange_rate_reads_usd_jpy_env(monkeypatch) -> None:
    monkeypatch.setenv("USD_JPY_EXCHANGE_RATE", "152.5")
    assert resolve_usd_jpy_exchange_rate() == 152.5


def test_endpoint_status_reports_unconfigured_by_default(monkeypatch) -> None:
    monkeypatch.delenv("FASHIONPHILE_API_URL", raising=False)
    monkeypatch.delenv("YAHOO_AUCTION_DATA_SOURCE", raising=False)
    monkeypatch.delenv("YAHOO_CLIENT_ID", raising=False)

    fashionphile = fashionphile_endpoint_status()
    yahoo = yahoo_auction_endpoint_status()

    assert fashionphile.configured is False
    assert yahoo.configured is False
    assert DataStatus.FIXTURE.value == "FIXTURE"
