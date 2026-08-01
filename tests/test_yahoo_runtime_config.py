"""Tests for DomesticMarketRuntimeConfig HTTP transport settings."""

from __future__ import annotations

from marketplace.domestic_market import DomesticMarketRuntimeConfig, TransportMode


def test_domestic_market_runtime_config_defaults() -> None:
    config = DomesticMarketRuntimeConfig.default()

    assert config.endpoint is None
    assert config.timeout_seconds == 10
    assert config.retry_count == 3
    assert config.use_fixture is True
    assert config.enable_live is False
    assert config.transport_mode is TransportMode.FIXTURE


def test_domestic_market_runtime_config_custom_http_settings() -> None:
    config = DomesticMarketRuntimeConfig(
        use_fixture=True,
        enable_live=True,
        api_key="live-key",
        transport_mode=TransportMode.LIVE,
        endpoint="https://example.invalid/yahoo-auction/sold",
        timeout_seconds=5,
        retry_count=2,
    )

    assert config.endpoint == "https://example.invalid/yahoo-auction/sold"
    assert config.timeout_seconds == 5
    assert config.retry_count == 2
    assert config.is_http_transport_configured() is True


def test_domestic_market_runtime_config_http_requires_endpoint_and_api_key() -> None:
    missing_endpoint = DomesticMarketRuntimeConfig(
        enable_live=True,
        api_key="live-key",
        transport_mode=TransportMode.LIVE,
    )
    missing_api_key = DomesticMarketRuntimeConfig(
        enable_live=True,
        transport_mode=TransportMode.LIVE,
        endpoint="https://example.invalid/yahoo-auction/sold",
    )

    assert missing_endpoint.is_http_transport_configured() is False
    assert missing_api_key.is_http_transport_configured() is False
