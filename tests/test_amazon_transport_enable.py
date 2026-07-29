"""Production-readiness validation for Amazon with AMAZON_USE_TRANSPORT enabled."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from config import settings
from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_marketplace import AmazonMarketplace, create_amazon_marketplace
from marketplace.amazon_response_parser import AmazonResponseParser
from marketplace.amazon_settings import AmazonConfig
from marketplace.marketplace_factory import create_marketplace
from models.marketplace_search_result import SEARCH_SUCCESS
from models.product import Product
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy
from product_identity.enums import IdentifierType
from product_identity.extractor import extract_from_listing

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "live-validation-amazon-secret-key"
ACCESS_KEY = "AKIA_LIVE_VALIDATION_KEY"
PARTNER_TAG = "live-partner-tag-001"


def _transport_config(**overrides) -> AmazonConfig:
    defaults = dict(
        marketplace_id="A1VC38T7YXB528",
        default_currency="JPY",
        default_language="ja_JP",
        max_results=20,
        timeout_seconds=10,
        retry_count=0,
        enabled=True,
        demo_enabled=True,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        partner_tag=PARTNER_TAG,
        region="us-west-2",
        api_host="webservices.amazon.co.jp",
        use_transport=True,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _product() -> Product:
    return Product(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


def test_environment_flag_loads_use_transport_true(monkeypatch) -> None:
    monkeypatch.setenv("AMAZON_USE_TRANSPORT", "true")
    monkeypatch.setattr(settings, "AMAZON_USE_TRANSPORT", True)

    config = AmazonConfig.from_env()

    assert config.use_transport is True


def test_environment_flag_loads_use_transport_false_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AMAZON_USE_TRANSPORT", raising=False)
    monkeypatch.setattr(settings, "AMAZON_USE_TRANSPORT", False)

    config = AmazonConfig.from_env()

    assert config.use_transport is False


def test_factory_flow_uses_transport_enabled_api_client() -> None:
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))
    transport_calls: list[str] = []
    signed_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        signed_headers.update(dict(request.headers))
        return httpx.Response(200, json=payload)

    config = _transport_config()
    api_client = AmazonApiClient(config=config, client=_mock_client(handler))
    marketplace = create_amazon_marketplace(client=api_client, config=config)

    assert isinstance(marketplace, AmazonMarketplace)
    assert marketplace.config.use_transport is True
    assert isinstance(marketplace._client, AmazonApiClient)

    from utils.transport.transport import HttpTransport

    original_post = HttpTransport.post

    def _recording_post(self, url, **kwargs):
        transport_calls.append("called")
        signed_headers.update(kwargs.get("headers") or {})
        return original_post(self, url, **kwargs)

    with patch.object(HttpTransport, "post", _recording_post):
        result = marketplace.search(_product())

    assert transport_calls == ["called"]
    assert signed_headers["authorization"].startswith("AWS4-HMAC-SHA256")
    assert signed_headers["x-amz-date"]
    assert result.status == SEARCH_SUCCESS
    assert result.selected_listing is not None


def test_create_marketplace_amazon_jp_factory_with_transport_client() -> None:
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))
    transport_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    api_client = AmazonApiClient(config=config, client=_mock_client(handler))
    marketplace = create_marketplace(
        "amazon_jp",
        amazon_settings=config,
        amazon_client=api_client,
    )

    assert isinstance(marketplace, AmazonMarketplace)
    assert marketplace._client is api_client
    assert marketplace.config.use_transport is True

    from utils.transport.transport import HttpTransport

    original_post = HttpTransport.post

    def _recording_post(self, url, **kwargs):
        transport_calls.append("called")
        return original_post(self, url, **kwargs)

    with patch.object(HttpTransport, "post", _recording_post):
        result = marketplace.search(_product())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS


def test_create_marketplace_amazon_settings_propagate_use_transport() -> None:
    config = _transport_config()
    api_client = AmazonApiClient(config=config)
    marketplace = create_marketplace(
        "amazon",
        amazon_settings=config,
        amazon_client=api_client,
    )

    assert isinstance(marketplace._client, AmazonApiClient)
    assert marketplace.config.use_transport is True
    assert marketplace.config.retry_count == 0


def test_search_pipeline_transport_adapter_parser_and_result() -> None:
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())
    parser = AmazonResponseParser()
    parsed = parser.parse(payload, source_query=result.query)
    meta = parser.parse_metadata(payload)

    assert captured_headers["authorization"].startswith("AWS4-HMAC-SHA256")
    assert result.status == SEARCH_SUCCESS
    assert result.query == "GUCCI 456126"
    assert result.total_results == meta[0] == 3
    assert result.next_page_token == meta[1] == "page-2-token"
    assert len(result.listings) == len(parsed) == 3
    assert len(result.valid_listings) >= 1

    listing = result.listings[0]
    assert listing.listing_id == "B0TEST2001"
    assert listing.title == "GUCCI GG Marmont Wallet Black"
    assert listing.brand == "GUCCI"
    assert listing.price_jpy == Decimal("128000")
    assert listing.seller_name == "Amazon.co.jp"
    assert listing.is_amazon_seller is True
    assert listing.is_prime is True
    assert listing.points_jpy == Decimal("1280")
    assert listing.shipping_jpy == Decimal("0")


def test_search_pipeline_ranking_compatibility_with_transport() -> None:
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())
    comparator = PriceComparator()

    highest = comparator.select_from_listings(
        result.valid_listings,
        strategy=PriceSelectionStrategy.HIGHEST,
    )
    lowest = comparator.select_from_listings(
        result.valid_listings,
        strategy=PriceSelectionStrategy.LOWEST,
    )

    assert highest is not None
    assert lowest is not None
    assert result.selected_price_jpy == highest[1]
    assert highest[1] >= lowest[1]
    assert len(result.valid_listings) >= 2


def test_search_pipeline_product_identity_compatibility_with_transport() -> None:
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())
    profile = extract_from_listing(result.listings[0])
    sku_values = [
        identifier.normalized_value
        for identifier in profile.structured_identifiers
        if identifier.identifier_type is IdentifierType.SKU and identifier.normalized_value
    ]

    assert result.listings[0].listing_id == "B0TEST2001"
    assert profile.listing_id == "B0TEST2001"
    assert sku_values == ["B0TEST2001"]
    assert profile.brand == "gucci"


def test_fake_amazon_client_regression_unchanged_with_transport_config_enabled() -> None:
    payload = json.loads((FIXTURES / "amazon_search_normal.json").read_text(encoding="utf-8"))
    fake = FakeAmazonClient(payload)
    config = _transport_config()

    marketplace = AmazonMarketplace(client=fake, config=config)
    result = marketplace.search(_product())

    assert fake.last_query == "GUCCI 456126"
    assert result.status == SEARCH_SUCCESS
    assert len(result.valid_listings) >= 1
    assert result.listings[0].listing_id == "B0TEST1234"

    direct = fake.search_items(query="manual-query", max_results=5, page=2, page_token="page-2")
    assert direct == payload
    assert fake.last_query == "manual-query"
    assert fake.last_max_results == 5
    assert fake.last_page == 2
    assert fake.last_page_token == "page-2"


def test_retry_count_zero_preserves_single_request_on_429() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"Errors": []})

    config = _transport_config(retry_count=0)
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())

    assert attempts["count"] == 1
    assert result.status == "error"


def test_retry_count_zero_preserves_single_request_on_timeout() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.TimeoutException("timeout")

    config = _transport_config(retry_count=0)
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())

    assert attempts["count"] == 1
    assert result.status == "error"


def test_logging_security_transport_enabled_full_pipeline(caplog) -> None:
    caplog.set_level(logging.INFO)
    payload = json.loads((FIXTURES / "amazon_search_multiple.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = AmazonMarketplace(
        client=AmazonApiClient(config=config, client=_mock_client(handler)),
        config=config,
    )
    marketplace.search(_product())

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    assert transport_records
    combined = "\n".join(record.getMessage() for record in caplog.records)
    for record in caplog.records:
        combined += str(getattr(record, "transport", {}))

    assert SECRET_KEY not in combined
    assert ACCESS_KEY not in combined
    assert "Signature=" not in combined or "***" in combined
