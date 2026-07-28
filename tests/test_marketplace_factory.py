"""Unit tests for marketplace.marketplace_factory."""

import pytest

from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.amazon_settings import AmazonConfig
from marketplace.base_marketplace import BaseMarketplace
from marketplace.local_marketplace import LocalMarketplace
from marketplace.marketplace_factory import create_marketplace, get_all_marketplaces
from marketplace.yahoo_marketplace import YahooMarketplace
from marketplace.yahoo_settings import YahooApiSettings


def _yahoo_settings() -> YahooApiSettings:
    return YahooApiSettings(
        client_id="dummy-test-client-id",
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
    )


def _amazon_settings() -> AmazonConfig:
    return AmazonConfig(
        marketplace_id="A1VC38T7YXB528",
        default_currency="JPY",
        default_language="ja_JP",
        max_results=20,
        timeout_seconds=10,
        retry_count=0,
        enabled=True,
        demo_enabled=True,
    )


def test_create_local_marketplace() -> None:
    marketplace = create_marketplace("local")
    assert isinstance(marketplace, LocalMarketplace)
    assert isinstance(marketplace, BaseMarketplace)


def test_create_yahoo_marketplace() -> None:
    marketplace = create_marketplace("yahoo", yahoo_settings=_yahoo_settings())
    assert isinstance(marketplace, YahooMarketplace)


def test_create_amazon_marketplace() -> None:
    marketplace = create_marketplace("amazon_jp", amazon_settings=_amazon_settings())
    assert isinstance(marketplace, AmazonMarketplace)


def test_case_insensitive() -> None:
    marketplace = create_marketplace("LOCAL")
    assert isinstance(marketplace, LocalMarketplace)


def test_whitespace_normalization() -> None:
    marketplace = create_marketplace("  local  ")
    assert isinstance(marketplace, LocalMarketplace)


def test_unsupported_marketplace_error() -> None:
    with pytest.raises(ValueError, match="Unsupported marketplace"):
        create_marketplace("amazon_us")


@pytest.mark.parametrize(
    "name,message",
    [
        ("rakuten", "Rakuten marketplace is not yet implemented"),
        ("mercari", "Mercari marketplace is not yet implemented"),
    ],
)
def test_not_implemented_marketplaces(name: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_marketplace(name)


def test_get_all_marketplaces() -> None:
    marketplaces = get_all_marketplaces(
        yahoo_settings=_yahoo_settings(),
        amazon_settings=_amazon_settings(),
    )
    assert len(marketplaces) == 3
    assert isinstance(marketplaces[0], LocalMarketplace)
    assert isinstance(marketplaces[1], YahooMarketplace)
    assert isinstance(marketplaces[2], AmazonMarketplace)
