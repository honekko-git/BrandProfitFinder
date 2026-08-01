"""Tests for Yahoo Auction HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from marketplace.domestic_market import DomesticMarketRuntimeConfig, TransportMode
from marketplace.domestic_market.yahoo_auction import (
    YahooAuctionAuthenticationError,
    YahooAuctionHTTPTransport,
    YahooAuctionResponseError,
    YahooAuctionTransportError,
)


def _config(**overrides) -> DomesticMarketRuntimeConfig:
    defaults = dict(
        use_fixture=False,
        enable_live=True,
        api_key="test-api-key",
        transport_mode=TransportMode.LIVE,
        endpoint="https://example.invalid/yahoo-auction/sold",
        timeout_seconds=10,
        retry_count=3,
    )
    defaults.update(overrides)
    return DomesticMarketRuntimeConfig(**defaults)


def _sample_payload() -> dict[str, object]:
    return {
        "items": [
            {
                "title": "Chanel Classic Wallet Black Caviar",
                "sold_price": 155000,
                "url": "https://example.invalid/chanel-1",
                "sold_date": "2026-07-01",
            },
            {
                "title": "Chanel CC Wallet Medium",
                "sold_price": 160000,
            },
        ]
    }


def test_yahoo_http_transport_builds_request_params() -> None:
    params = YahooAuctionHTTPTransport.build_request_params(
        "Chanel Wallet",
        api_key="secret-key",
    )

    assert params == {"query": "Chanel Wallet", "appid": "secret-key"}


def test_yahoo_http_transport_search_builds_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_sample_payload())

    transport = YahooAuctionHTTPTransport(
        config=_config(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    items = transport.search_sold_items("Chanel Wallet")

    assert captured["params"] == {"query": "Chanel Wallet", "appid": "test-api-key"}
    assert "Chanel+Wallet" in str(captured["url"]) or "Chanel%20Wallet" in str(captured["url"])
    assert len(items) == 2
    assert items[0]["sold_price"] == 155000


def test_yahoo_http_transport_timeout_raises_transport_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    transport = YahooAuctionHTTPTransport(
        config=_config(timeout_seconds=0.001, retry_count=1),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(YahooAuctionTransportError, match="timed out"):
        transport.search_sold_items("Chanel Wallet")


def test_yahoo_http_transport_retries_server_errors() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=_sample_payload())

    transport = YahooAuctionHTTPTransport(
        config=_config(retry_count=3),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    items = transport.search_sold_items("Chanel Wallet")

    assert attempts["count"] == 3
    assert len(items) == 2


def test_yahoo_http_transport_authentication_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = YahooAuctionHTTPTransport(
        config=_config(retry_count=1),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(YahooAuctionAuthenticationError, match="authentication failed"):
        transport.search_sold_items("Chanel Wallet")


def test_yahoo_http_transport_invalid_json_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    transport = YahooAuctionHTTPTransport(
        config=_config(retry_count=1),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(YahooAuctionResponseError, match="valid JSON"):
        transport.search_sold_items("Chanel Wallet")


def test_yahoo_http_transport_invalid_item_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{"title": "Broken Item"}]})

    transport = YahooAuctionHTTPTransport(
        config=_config(retry_count=1),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(YahooAuctionResponseError, match="missing required fields"):
        transport.search_sold_items("Chanel Wallet")


def test_yahoo_http_transport_requires_api_key() -> None:
    transport = YahooAuctionHTTPTransport(config=_config(api_key=None))

    with pytest.raises(YahooAuctionAuthenticationError, match="API key"):
        transport.search_sold_items("Chanel Wallet")
