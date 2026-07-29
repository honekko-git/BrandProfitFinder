"""Tests for unified marketplace client resolution and factory integration."""

from __future__ import annotations

import httpx
import pytest

from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.amazon_settings import AmazonConfig
from marketplace.marketplace_client_factory import (
    resolve_amazon_client,
    resolve_rakuten_client,
    resolve_yahoo_client,
)
from marketplace.marketplace_factory import create_marketplace
from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient
from marketplace.rakuten_marketplace import RakutenMarketplace
from marketplace.rakuten_settings import RakutenConfig
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_marketplace import YahooMarketplace
from marketplace.yahoo_settings import YahooApiSettings


def _rakuten_config(**overrides) -> RakutenConfig:
    defaults = dict(
        application_id="dummy-app-id",
        access_key="dummy-access-key",
        affiliate_id="",
        base_url="https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
        use_transport=False,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


def _yahoo_settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id="dummy-test-client-id",
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
        use_transport=False,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _amazon_config(**overrides) -> AmazonConfig:
    defaults = dict(
        marketplace_id="A1VC38T7YXB528",
        default_currency="JPY",
        default_language="ja_JP",
        max_results=20,
        timeout_seconds=10,
        retry_count=0,
        enabled=True,
        demo_enabled=False,
        access_key="",
        secret_key="",
        partner_tag="",
        region="us-west-2",
        api_host="webservices.amazon.co.jp",
        use_transport=False,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


class _InjectedRakutenClient(FakeRakutenClient):
    """Distinct fake client for injection priority tests."""


class _InjectedAmazonClient(FakeAmazonClient):
    """Distinct fake client for injection priority tests."""


class _InjectedYahooClient(YahooApiClient):
    """Distinct Yahoo client for injection priority tests."""


# --- Injection priority ---


def test_rakuten_explicit_client_wins_over_demo_and_live() -> None:
    injected = _InjectedRakutenClient({"Items": []})
    config = _rakuten_config(demo_enabled=True, use_transport=True)

    client = resolve_rakuten_client(injected, config)

    assert client is injected


def test_amazon_explicit_client_wins_over_demo_and_live() -> None:
    injected = _InjectedAmazonClient({"items": []})
    config = _amazon_config(
        demo_enabled=True,
        access_key="AKIA_TEST",
        secret_key="secret",
        partner_tag="tag-001",
        use_transport=True,
    )

    client = resolve_amazon_client(injected, config)

    assert client is injected


def test_yahoo_explicit_client_wins_over_live() -> None:
    injected = _InjectedYahooClient(settings=_yahoo_settings(use_transport=True))
    config = _yahoo_settings(use_transport=True)

    client = resolve_yahoo_client(injected, config)

    assert client is injected


# --- Demo resolution ---


def test_rakuten_demo_returns_fake_client() -> None:
    config = _rakuten_config(demo_enabled=True)

    client = resolve_rakuten_client(None, config)

    assert isinstance(client, FakeRakutenClient)


def test_amazon_demo_returns_fake_client() -> None:
    config = _amazon_config(demo_enabled=True)

    client = resolve_amazon_client(None, config)

    assert isinstance(client, FakeAmazonClient)


def test_yahoo_demo_has_no_fake_client() -> None:
    client = resolve_yahoo_client(None, _yahoo_settings())

    assert isinstance(client, YahooApiClient)


# --- Live resolution ---


def test_rakuten_live_returns_api_client() -> None:
    config = _rakuten_config(demo_enabled=False)

    client = resolve_rakuten_client(None, config)

    assert isinstance(client, RakutenApiClient)
    assert client.settings is config


def test_yahoo_live_returns_api_client() -> None:
    config = _yahoo_settings()

    client = resolve_yahoo_client(None, config)

    assert isinstance(client, YahooApiClient)
    assert client.settings is config


def test_amazon_live_returns_api_client() -> None:
    config = _amazon_config(
        demo_enabled=False,
        access_key="AKIA_TEST",
        secret_key="secret",
        partner_tag="tag-001",
    )

    client = resolve_amazon_client(None, config)

    assert isinstance(client, AmazonApiClient)
    assert client.config is config


# --- None resolution ---


def test_rakuten_no_credentials_returns_none() -> None:
    config = _rakuten_config(
        demo_enabled=False,
        application_id="",
        access_key="",
    )

    assert resolve_rakuten_client(None, config) is None


def test_amazon_no_credentials_returns_none() -> None:
    config = _amazon_config(demo_enabled=False)

    assert resolve_amazon_client(None, config) is None


def test_yahoo_no_credentials_returns_none() -> None:
    config = _yahoo_settings(client_id="", enabled=True)

    assert resolve_yahoo_client(None, config) is None


def test_rakuten_disabled_returns_none_without_demo() -> None:
    config = _rakuten_config(enabled=False, demo_enabled=False)

    assert resolve_rakuten_client(None, config) is None


# --- Factory compatibility ---


def test_create_marketplace_rakuten_uses_resolver_demo_client() -> None:
    marketplace = create_marketplace(
        "rakuten",
        rakuten_settings=_rakuten_config(demo_enabled=True),
    )

    assert isinstance(marketplace, RakutenMarketplace)
    assert isinstance(marketplace._client, FakeRakutenClient)


def test_create_marketplace_yahoo_uses_resolver_live_client() -> None:
    marketplace = create_marketplace("yahoo", yahoo_settings=_yahoo_settings())

    assert isinstance(marketplace, YahooMarketplace)
    assert isinstance(marketplace._client, YahooApiClient)


def test_create_marketplace_yahoo_accepts_yahoo_client_override() -> None:
    injected = _InjectedYahooClient(settings=_yahoo_settings())
    marketplace = create_marketplace(
        "yahoo",
        yahoo_settings=_yahoo_settings(),
        yahoo_client=injected,
    )

    assert marketplace._client is injected


def test_create_marketplace_amazon_jp_uses_resolver_demo_client() -> None:
    marketplace = create_marketplace(
        "amazon_jp",
        amazon_settings=_amazon_config(demo_enabled=True),
    )

    assert isinstance(marketplace, AmazonMarketplace)
    assert isinstance(marketplace._client, FakeAmazonClient)


def test_create_marketplace_rakuten_accepts_rakuten_client_override() -> None:
    injected = _InjectedRakutenClient({"Items": []})
    marketplace = create_marketplace(
        "rakuten",
        rakuten_settings=_rakuten_config(demo_enabled=True),
        rakuten_client=injected,
    )

    assert marketplace._client is injected


def test_create_marketplace_amazon_accepts_amazon_client_override() -> None:
    injected = _InjectedAmazonClient({"items": []})
    marketplace = create_marketplace(
        "amazon_jp",
        amazon_settings=_amazon_config(demo_enabled=True),
        amazon_client=injected,
    )

    assert marketplace._client is injected


# --- Transport flag propagation ---


@pytest.mark.parametrize(
    ("resolver", "config_factory", "expected_type"),
    [
        (resolve_rakuten_client, lambda: _rakuten_config(demo_enabled=False, use_transport=True), RakutenApiClient),
        (resolve_yahoo_client, lambda: _yahoo_settings(use_transport=True), YahooApiClient),
        (
            resolve_amazon_client,
            lambda: _amazon_config(
                demo_enabled=False,
                use_transport=True,
                access_key="AKIA_TEST",
                secret_key="secret",
                partner_tag="tag-001",
            ),
            AmazonApiClient,
        ),
    ],
)
def test_resolver_created_api_client_receives_transport_settings(
    resolver,
    config_factory,
    expected_type,
) -> None:
    config = config_factory()
    client = resolver(None, config)

    assert isinstance(client, expected_type)
    if isinstance(client, RakutenApiClient):
        assert client.settings.use_transport is True
    elif isinstance(client, YahooApiClient):
        assert client.settings.use_transport is True
    elif isinstance(client, AmazonApiClient):
        assert client.config.use_transport is True


def test_factory_rakuten_transport_flag_propagates_to_api_client() -> None:
    config = _rakuten_config(demo_enabled=False, use_transport=True)
    marketplace = create_marketplace("rakuten", rakuten_settings=config)

    assert isinstance(marketplace._client, RakutenApiClient)
    assert marketplace._client.settings.use_transport is True


def test_factory_yahoo_transport_flag_propagates_to_api_client() -> None:
    config = _yahoo_settings(use_transport=True)
    marketplace = create_marketplace("yahoo", yahoo_settings=config)

    assert isinstance(marketplace._client, YahooApiClient)
    assert marketplace._client.settings.use_transport is True


def test_factory_amazon_transport_flag_propagates_to_api_client() -> None:
    config = _amazon_config(
        demo_enabled=False,
        use_transport=True,
        access_key="AKIA_TEST",
        secret_key="secret",
        partner_tag="tag-001",
    )
    marketplace = create_marketplace("amazon_jp", amazon_settings=config)

    assert isinstance(marketplace._client, AmazonApiClient)
    assert marketplace._client.config.use_transport is True


def test_factory_yahoo_client_override_preserves_transport_settings() -> None:
    config = _yahoo_settings(use_transport=True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": 0, "totalResultsAvailable": 0, "totalResultsReturned": 0})

    injected = YahooApiClient(
        settings=config,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    marketplace = create_marketplace(
        "yahoo",
        yahoo_settings=config,
        yahoo_client=injected,
    )

    assert marketplace._client is injected
    assert marketplace._client.settings.use_transport is True
