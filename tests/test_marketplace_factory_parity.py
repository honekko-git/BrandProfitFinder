"""Factory behavior parity validation after unified client resolver migration."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from config.constants import (
    MARKETPLACE_AMAZON_JP,
    MARKETPLACE_LOCAL,
    MARKETPLACE_RAKUTEN,
    MARKETPLACE_YAHOO,
    MARKETPLACE_YAHOO_AUCTION,
)
from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.amazon_settings import AmazonConfig
from marketplace.marketplace_client_factory import (
    resolve_amazon_client,
    resolve_rakuten_client,
    resolve_yahoo_client,
)
from marketplace.marketplace_factory import create_marketplace, get_all_marketplaces
from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient
from marketplace.rakuten_marketplace import RakutenMarketplace
from marketplace.rakuten_settings import RakutenConfig
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_marketplace import YahooMarketplace
from marketplace.yahoo_settings import YahooApiSettings
from models.marketplace_search_result import MarketplaceSearchResult, SEARCH_SUCCESS
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_results
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from price_compare.ranking_engine import RankingEngine, RankingSortKey
from product_identity.enums import IdentifierType
from product_identity.extractor import extract_from_listing
from utils.transport.models import TransportResponse

FIXTURES = Path(__file__).parent / "fixtures"

ACCESS_KEY = "AKIA_FACTORY_PARITY_KEY"
SECRET_KEY = "factory-parity-secret-key"
PARTNER_TAG = "factory-parity-partner"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _product_rakuten_amazon() -> Product:
    return Product(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )


def _product_yahoo() -> Product:
    return Product(
        name="Gucci Marmont Bag",
        brand="Gucci",
        model="GG-MARMONT",
        sku="4901234567890",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )


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
        demo_enabled=True,
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
        max_retries=0,
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
        demo_enabled=True,
        access_key="",
        secret_key="",
        partner_tag="",
        region="us-west-2",
        api_host="webservices.amazon.co.jp",
        use_transport=False,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


def _transport_response(payload: dict[str, Any]) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode("utf-8"),
        elapsed_seconds=0.01,
        retry_count=0,
    )


def _search_result_snapshot(result: MarketplaceSearchResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "query": result.query,
        "marketplace_name": result.marketplace_name,
        "total_results": result.total_results,
        "next_page_token": result.next_page_token,
        "metadata": result.metadata,
        "selected_listing_id": result.selected_listing.listing_id if result.selected_listing else None,
        "selected_price_jpy": str(result.selected_price_jpy) if result.selected_price_jpy is not None else None,
        "valid_listing_ids": [listing.listing_id for listing in result.valid_listings],
        "listing_count": len(result.listings),
        "error_message": result.error_message,
    }


def _listing_snapshots(listings) -> list[dict[str, Any]]:
    return [
        {
            "listing_id": listing.listing_id,
            "title": listing.title,
            "brand": listing.brand,
            "price_jpy": str(listing.price_jpy),
            "shipping_jpy": str(listing.shipping_jpy),
            "listing_url": listing.listing_url,
            "sku": listing.sku,
            "jan_code": listing.jan_code,
        }
        for listing in listings
    ]


def _identity_snapshot(listing) -> dict[str, Any]:
    profile = extract_from_listing(listing)
    sku_values = [
        identifier.normalized_value
        for identifier in profile.structured_identifiers
        if identifier.identifier_type is IdentifierType.SKU and identifier.normalized_value
    ]
    return {
        "listing_id": profile.listing_id,
        "brand": profile.brand,
        "jan": profile.jan,
        "sku_identifiers": tuple(sku_values),
        "marketplace": profile.marketplace,
    }


def _profit_snapshot(result: MarketplaceSearchResult, calculator: ProfitCalculator) -> dict[str, Any]:
    price_result = calculate_profit_from_search_results([result], calculator)[0]
    return {
        "domestic_sale_price_jpy": str(price_result.domestic_sale_price_jpy),
        "profit_jpy": str(price_result.profit_jpy) if price_result.profit_jpy is not None else None,
        "marketplace_fee_jpy": str(price_result.marketplace_fee_jpy),
        "calculation_status": price_result.calculation_status,
    }


def _ranking_snapshot(result: MarketplaceSearchResult, calculator: ProfitCalculator) -> list[str]:
    price_results = calculate_profit_from_search_results([result], calculator)
    ranked = RankingEngine().rank(price_results, sort_key=RankingSortKey.PROFIT, descending=True)
    return [item.product.name if item.product else "" for item in ranked]


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


# --- 1. Rakuten parity ---


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rakuten_search_normal.json",
        "rakuten_search_multiple.json",
        "rakuten_search_empty.json",
    ],
)
def test_rakuten_manual_injection_matches_resolver_demo_for_fixture(fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    config = _rakuten_config(demo_enabled=True)
    product = _product_rakuten_amazon()

    manual = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=FakeRakutenClient(payload),
    )
    resolver_client = resolve_rakuten_client(None, config, demo_payload=payload)
    resolver_path = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=resolver_client,
    )

    manual_result = manual.search(product)
    resolver_result = resolver_path.search(product)

    assert isinstance(manual._client, FakeRakutenClient)
    assert isinstance(resolver_path._client, FakeRakutenClient)
    assert _search_result_snapshot(manual_result) == _search_result_snapshot(resolver_result)


def test_rakuten_empty_manual_injection_matches_demo_resolver_factory() -> None:
    config = _rakuten_config(demo_enabled=True)
    product = _product_rakuten_amazon()

    manual = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=FakeRakutenClient(),
    )
    resolver_demo = create_marketplace("rakuten", rakuten_settings=config)

    manual_result = manual.search(product)
    resolver_result = resolver_demo.search(product)

    assert type(manual._client) is type(resolver_demo._client) is FakeRakutenClient
    assert _search_result_snapshot(manual_result) == _search_result_snapshot(resolver_result)


def test_rakuten_fixture_metadata_and_ranking_parity_between_manual_and_resolver() -> None:
    payload = _fixture("rakuten_search_multiple.json")
    config = _rakuten_config(demo_enabled=True)
    product = _product_rakuten_amazon()
    calculator = ProfitCalculator(ProfitConfig(marketplace_fee_rate=Decimal("0")))

    manual = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=FakeRakutenClient(payload),
    )
    resolver_demo = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=resolve_rakuten_client(None, config, demo_payload=payload),
    )

    manual_result = manual.search(product)
    resolver_result = resolver_demo.search(product)

    assert manual_result.metadata == resolver_result.metadata
    assert manual_result.total_results == resolver_result.total_results
    assert [listing.listing_id for listing in manual_result.valid_listings] == [
        listing.listing_id for listing in resolver_result.valid_listings
    ]
    assert _ranking_snapshot(manual_result, calculator) == _ranking_snapshot(resolver_result, calculator)


# --- 2. Amazon parity ---


@pytest.mark.parametrize(
    "fixture_name",
    [
        "amazon_search_normal.json",
        "amazon_search_multiple.json",
        "amazon_search_empty.json",
    ],
)
def test_amazon_manual_injection_matches_resolver_demo_for_fixture(fixture_name: str) -> None:
    payload = _fixture(fixture_name)
    config = _amazon_config(demo_enabled=True)
    product = _product_rakuten_amazon()
    calculator = ProfitCalculator(
        ProfitConfig(
            international_shipping_jpy=Decimal("2500"),
            customs_duty_rate=Decimal("0.08"),
            import_tax_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("800"),
            marketplace_fee_rate=Decimal("0.12"),
            other_costs_jpy=Decimal("500"),
        )
    )

    manual = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=FakeAmazonClient(payload),
    )
    resolver_path = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=resolve_amazon_client(None, config, demo_payload=payload),
    )

    manual_result = manual.search(product)
    resolver_result = resolver_path.search(product)

    assert isinstance(manual._client, FakeAmazonClient)
    assert isinstance(resolver_path._client, FakeAmazonClient)
    assert _listing_snapshots(manual_result.listings) == _listing_snapshots(resolver_result.listings)
    assert _profit_snapshot(manual_result, calculator) == _profit_snapshot(resolver_result, calculator)


def test_amazon_identity_extraction_parity_manual_vs_resolver_demo() -> None:
    payload = _fixture("amazon_search_normal.json")
    config = _amazon_config(demo_enabled=True)
    product = _product_rakuten_amazon()

    manual = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=FakeAmazonClient(payload),
    )
    resolver_path = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=resolve_amazon_client(None, config, demo_payload=payload),
    )

    manual_listing = manual.search(product).listings[0]
    resolver_listing = resolver_path.search(product).listings[0]

    assert _identity_snapshot(manual_listing) == _identity_snapshot(resolver_listing)


def test_amazon_empty_manual_fake_matches_resolver_demo_factory() -> None:
    config = _amazon_config(demo_enabled=True)
    product = _product_rakuten_amazon()

    manual = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=FakeAmazonClient(),
    )
    resolver_demo = create_marketplace("amazon_jp", amazon_settings=config)

    assert type(manual._client) is type(resolver_demo._client) is FakeAmazonClient
    assert _search_result_snapshot(manual.search(product)) == _search_result_snapshot(resolver_demo.search(product))


# --- 3. Yahoo parity ---


def test_yahoo_explicit_client_matches_resolver_created_client() -> None:
    payload = _fixture("yahoo_item_search_success.json")
    config = _yahoo_settings(use_transport=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    explicit_client = YahooApiClient(
        settings=config,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    resolver_client = resolve_yahoo_client(None, config)
    assert isinstance(resolver_client, YahooApiClient)

    explicit_marketplace = create_marketplace(
        "yahoo",
        yahoo_settings=config,
        yahoo_client=explicit_client,
    )
    resolver_marketplace = create_marketplace("yahoo", yahoo_settings=config)

    assert explicit_marketplace._client.settings.client_id == resolver_marketplace._client.settings.client_id
    assert explicit_marketplace._client.settings.use_transport == resolver_marketplace._client.settings.use_transport
    assert explicit_marketplace._client.settings.base_url == resolver_marketplace._client.settings.base_url


def test_yahoo_search_behavior_parity_explicit_vs_resolver() -> None:
    payload = _fixture("yahoo_item_search_success.json")
    config = _yahoo_settings(use_transport=False)
    product = _product_yahoo()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    explicit = create_marketplace(
        "yahoo",
        yahoo_settings=config,
        yahoo_client=YahooApiClient(settings=config, client=mock_client),
    )
    resolver = create_marketplace("yahoo", yahoo_settings=config)

    with patch.object(YahooApiClient, "from_settings", return_value=YahooApiClient(settings=config, client=mock_client)):
        resolver_with_mock = create_marketplace("yahoo", yahoo_settings=config)

    explicit_result = explicit.search(product)
    resolver_result = resolver_with_mock.search(product)

    assert _search_result_snapshot(explicit_result) == _search_result_snapshot(resolver_result)


def test_yahoo_transport_flag_parity_explicit_vs_resolver() -> None:
    config = _yahoo_settings(use_transport=True)

    explicit = YahooApiClient(settings=config)
    resolver = resolve_yahoo_client(None, config)

    assert isinstance(resolver, YahooApiClient)
    assert explicit.settings.use_transport is True
    assert resolver.settings.use_transport is True
    assert explicit.settings.max_retries == resolver.settings.max_retries


# --- 4. Transport enabled factory flow ---


def test_rakuten_resolver_factory_transport_flow_reaches_http_transport() -> None:
    payload = _fixture("rakuten_search_normal.json")
    config = _rakuten_config(demo_enabled=False, use_transport=True)
    transport_calls: list[str] = []

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    marketplace = create_marketplace("rakuten", rakuten_settings=config)
    assert isinstance(marketplace._client, RakutenApiClient)
    assert marketplace.config.use_transport is True

    from utils.transport.transport import HttpTransport

    with patch.object(HttpTransport, "get", _recording_get):
        result = marketplace.search(_product_rakuten_amazon())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


def test_yahoo_resolver_factory_transport_flow_reaches_http_transport() -> None:
    payload = _fixture("yahoo_item_search_success.json")
    config = _yahoo_settings(use_transport=True)
    transport_calls: list[str] = []

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    marketplace = create_marketplace("yahoo", yahoo_settings=config)
    assert isinstance(marketplace._client, YahooApiClient)
    assert marketplace._client.settings.use_transport is True

    from utils.transport.transport import HttpTransport

    with patch.object(HttpTransport, "get", _recording_get):
        result = marketplace.search(_product_yahoo())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


def test_amazon_resolver_factory_transport_flow_reaches_http_transport() -> None:
    payload = _fixture("amazon_paapi_search_raw.json")
    config = _amazon_config(
        demo_enabled=False,
        use_transport=True,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        partner_tag=PARTNER_TAG,
    )
    transport_calls: list[str] = []

    def _recording_post(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    marketplace = create_marketplace("amazon_jp", amazon_settings=config)
    assert isinstance(marketplace._client, AmazonApiClient)
    assert marketplace.config.use_transport is True

    from utils.transport.transport import HttpTransport

    with patch.object(HttpTransport, "post", _recording_post):
        result = marketplace.search(_product_rakuten_amazon())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


@pytest.mark.parametrize(
    ("marketplace_name", "settings_factory", "expected_client_type", "transport_method"),
    [
        ("rakuten", lambda: _rakuten_config(demo_enabled=False, use_transport=True), RakutenApiClient, "get"),
        ("yahoo", lambda: _yahoo_settings(use_transport=True), YahooApiClient, "get"),
        (
            "amazon_jp",
            lambda: _amazon_config(
                demo_enabled=False,
                use_transport=True,
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                partner_tag=PARTNER_TAG,
            ),
            AmazonApiClient,
            "post",
        ),
    ],
)
def test_transport_enabled_create_marketplace_chain(
    marketplace_name: str,
    settings_factory,
    expected_client_type,
    transport_method: str,
) -> None:
    """Verify create_marketplace -> resolver -> ApiClient -> HttpTransport for each marketplace."""
    transport_calls: list[str] = []
    config = settings_factory()

    if marketplace_name == "rakuten":
        marketplace = create_marketplace("rakuten", rakuten_settings=config)
    elif marketplace_name == "yahoo":
        marketplace = create_marketplace("yahoo", yahoo_settings=config)
    else:
        marketplace = create_marketplace("amazon_jp", amazon_settings=config)

    assert isinstance(marketplace._client, expected_client_type)

    from utils.transport.transport import HttpTransport

    if transport_method == "get":
        payload = _fixture(
            "rakuten_search_normal.json" if marketplace_name == "rakuten" else "yahoo_item_search_success.json"
        )

        def _recording_get(self, url, **kwargs):
            transport_calls.append("called")
            return _transport_response(payload)

        patch_target = patch.object(HttpTransport, "get", _recording_get)
        product = _product_rakuten_amazon() if marketplace_name == "rakuten" else _product_yahoo()
    else:
        payload = _fixture("amazon_paapi_search_raw.json")

        def _recording_post(self, url, **kwargs):
            transport_calls.append("called")
            return _transport_response(payload)

        patch_target = patch.object(HttpTransport, "post", _recording_post)
        product = _product_rakuten_amazon()

    with patch_target:
        result = marketplace.search(product)

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


# --- 5. get_all_marketplaces ---


def test_get_all_marketplaces_returns_expected_marketplaces() -> None:
    marketplaces = get_all_marketplaces(
        yahoo_settings=_yahoo_settings(),
        rakuten_settings=_rakuten_config(demo_enabled=True),
        amazon_settings=_amazon_config(demo_enabled=True),
    )
    names = {marketplace.marketplace_name for marketplace in marketplaces}

    assert names == {
        MARKETPLACE_LOCAL,
        MARKETPLACE_YAHOO,
        MARKETPLACE_AMAZON_JP,
        MARKETPLACE_RAKUTEN,
        MARKETPLACE_YAHOO_AUCTION,
    }
    assert len(marketplaces) == 5


def test_get_all_marketplaces_resolves_usable_clients() -> None:
    marketplaces = get_all_marketplaces(
        yahoo_settings=_yahoo_settings(),
        rakuten_settings=_rakuten_config(demo_enabled=True),
        amazon_settings=_amazon_config(demo_enabled=True),
    )
    by_name = {marketplace.marketplace_name: marketplace for marketplace in marketplaces}

    assert isinstance(by_name[MARKETPLACE_RAKUTEN], RakutenMarketplace)
    assert isinstance(by_name[MARKETPLACE_RAKUTEN]._client, FakeRakutenClient)

    assert isinstance(by_name[MARKETPLACE_AMAZON_JP], AmazonMarketplace)
    assert isinstance(by_name[MARKETPLACE_AMAZON_JP]._client, FakeAmazonClient)

    assert isinstance(by_name[MARKETPLACE_YAHOO], YahooMarketplace)
    assert isinstance(by_name[MARKETPLACE_YAHOO]._client, YahooApiClient)


def test_get_all_marketplaces_makes_no_live_http_calls() -> None:
    from utils.transport.transport import HttpTransport

    with patch.object(httpx.Client, "get") as httpx_get, patch.object(httpx.Client, "post") as httpx_post, patch.object(
        HttpTransport, "get"
    ) as transport_get, patch.object(HttpTransport, "post") as transport_post:
        get_all_marketplaces(
            yahoo_settings=_yahoo_settings(),
            rakuten_settings=_rakuten_config(demo_enabled=True),
            amazon_settings=_amazon_config(demo_enabled=True),
        )

    assert httpx_get.call_count == 0
    assert httpx_post.call_count == 0
    assert transport_get.call_count == 0
    assert transport_post.call_count == 0


def test_get_all_marketplaces_live_config_without_demo_uses_api_clients_not_none() -> None:
    marketplaces = get_all_marketplaces(
        yahoo_settings=_yahoo_settings(use_transport=True),
        rakuten_settings=_rakuten_config(demo_enabled=False, use_transport=True),
        amazon_settings=_amazon_config(
            demo_enabled=False,
            use_transport=True,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            partner_tag=PARTNER_TAG,
        ),
    )
    by_name = {marketplace.marketplace_name: marketplace for marketplace in marketplaces}

    assert isinstance(by_name[MARKETPLACE_RAKUTEN]._client, RakutenApiClient)
    assert isinstance(by_name[MARKETPLACE_YAHOO]._client, YahooApiClient)
    assert isinstance(by_name[MARKETPLACE_AMAZON_JP]._client, AmazonApiClient)
    assert by_name[MARKETPLACE_RAKUTEN]._client.settings.use_transport is True
    assert by_name[MARKETPLACE_YAHOO]._client.settings.use_transport is True
    assert by_name[MARKETPLACE_AMAZON_JP]._client.config.use_transport is True
