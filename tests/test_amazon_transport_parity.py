"""Parity validation between legacy Amazon HTTP and Version 2 HttpTransport paths."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import httpx
import pytest

from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_exceptions import (
    AmazonApiError,
    AmazonAuthenticationError,
    AmazonClientError,
    AmazonMarketplaceError,
    AmazonRateLimitError,
    AmazonServerError,
)
from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.amazon_response_adapter import adapt_amazon_search_response
from marketplace.amazon_response_parser import AmazonResponseParser
from marketplace.amazon_settings import AmazonConfig
from models.product import Product
from product_identity.enums import IdentifierType
from product_identity.extractor import extract_from_listing

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "parity-test-amazon-secret-key"
ACCESS_KEY = "AKIA_PARITY_ACCESS_KEY"
PARTNER_TAG = "parity-partner-tag"


def _config(**overrides) -> AmazonConfig:
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
        use_transport=False,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


def _mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _legacy_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> AmazonApiClient:
    return AmazonApiClient(
        config=_config(use_transport=False, **config_overrides),
        client=_mock_client(handler),
    )


def _transport_client(
    handler: Callable[[httpx.Request], httpx.Response],
    **config_overrides,
) -> AmazonApiClient:
    return AmazonApiClient(
        config=_config(use_transport=True, **config_overrides),
        client=_mock_client(handler),
    )


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _listing_snapshots(listings) -> list[dict[str, Any]]:
    return [
        {
            "listing_id": listing.listing_id,
            "title": listing.title,
            "brand": listing.brand,
            "price_jpy": str(listing.price_jpy),
            "shipping_jpy": str(listing.shipping_jpy),
            "seller_name": listing.seller_name,
            "is_amazon_seller": listing.is_amazon_seller,
            "points_jpy": str(listing.points_jpy) if listing.points_jpy is not None else None,
            "is_prime": listing.is_prime,
            "listing_url": listing.listing_url,
            "sku": listing.sku,
            "jan_code": listing.jan_code,
        }
        for listing in listings
    ]


def _payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    return {
        "total_results": payload.get("total_results"),
        "next_page_token": payload.get("next_page_token"),
        "item_count": len(items) if isinstance(items, list) else 0,
    }


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


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "amazon_search_multiple.json",
        "amazon_search_normal.json",
        "amazon_search_empty.json",
    ],
)
def test_response_payload_parity_internal_fixture(fixture_name: str) -> None:
    payload = _fixture(fixture_name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy = _legacy_client(handler).search_items(query="gucci wallet")
    transport = _transport_client(handler).search_items(query="gucci wallet")

    assert legacy == transport
    assert legacy == payload
    assert _payload_metadata(legacy) == _payload_metadata(transport)


def test_response_payload_parity_paapi_raw_fixture() -> None:
    raw = _fixture("amazon_paapi_search_raw.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw)

    legacy = _legacy_client(handler).search_items(query="gucci wallet")
    transport = _transport_client(handler).search_items(query="gucci wallet")

    assert legacy == transport
    assert legacy["items"][0]["asin"] == "B0TEST1234"
    assert legacy["total_results"] == 3
    assert legacy["next_page_token"] == "2"


def test_fake_client_vs_transport_api_client_parser_parity() -> None:
    internal = _fixture("amazon_search_multiple.json")
    raw = _fixture("amazon_paapi_search_raw.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw)

    fake_payload = FakeAmazonClient(internal).search_items(query="gucci")
    transport_payload = _transport_client(handler).search_items(query="gucci")
    parser = AmazonResponseParser()

    fake_listings = parser.parse(fake_payload, source_query="gucci")
    transport_listings = parser.parse(transport_payload, source_query="gucci")

    assert len(fake_listings) == 3
    assert len(transport_listings) == 2
    assert fake_listings[0].listing_id == "B0TEST2001"
    assert transport_listings[0].listing_id == "B0TEST1234"
    assert fake_listings[0].brand == transport_listings[0].brand == "GUCCI"


def test_adapter_output_matches_parser_expectations() -> None:
    raw = _fixture("amazon_paapi_search_raw.json")
    internal = _fixture("amazon_search_normal.json")
    parser = AmazonResponseParser()

    adapted = adapt_amazon_search_response(raw)
    adapted_listings = parser.parse(adapted, source_query="gucci")
    internal_listings = parser.parse(internal, source_query="gucci")

    assert adapted_listings[0].listing_id == internal_listings[0].listing_id == "B0TEST1234"
    assert adapted_listings[0].title == internal_listings[0].title
    assert adapted_listings[0].price_jpy == internal_listings[0].price_jpy
    assert adapted_listings[0].brand == internal_listings[0].brand == "GUCCI"
    assert adapted_listings[0].seller_name == "Amazon.co.jp"
    assert adapted_listings[0].is_prime is True
    assert internal_listings[0].points_jpy is not None


def test_parser_listing_field_parity_legacy_vs_transport() -> None:
    payload = _fixture("amazon_search_multiple.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    parser = AmazonResponseParser()
    legacy_payload = _legacy_client(handler).search_items(query="gucci")
    transport_payload = _transport_client(handler).search_items(query="gucci")

    legacy_listings = parser.parse(legacy_payload, source_query="gucci")
    transport_listings = parser.parse(transport_payload, source_query="gucci")
    legacy_meta = parser.parse_metadata(legacy_payload)
    transport_meta = parser.parse_metadata(transport_payload)

    assert _listing_snapshots(legacy_listings) == _listing_snapshots(transport_listings)
    assert legacy_meta == transport_meta
    assert legacy_meta == (3, "page-2-token")
    assert legacy_listings[1].points_jpy == transport_listings[1].points_jpy


def test_product_identity_extraction_parity_legacy_vs_transport() -> None:
    payload = _fixture("amazon_search_multiple.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    parser = AmazonResponseParser()
    legacy_listings = parser.parse(_legacy_client(handler).search_items(query="gucci"), source_query="gucci")
    transport_listings = parser.parse(
        _transport_client(handler).search_items(query="gucci"),
        source_query="gucci",
    )

    assert _identity_snapshot(legacy_listings[0]) == _identity_snapshot(transport_listings[0])
    assert legacy_listings[0].listing_id == legacy_listings[0].sku == "B0TEST2001"
    assert _identity_snapshot(legacy_listings[0])["sku_identifiers"] == ("B0TEST2001",)


def test_product_identity_asin_maps_to_listing_id_and_sku() -> None:
    payload = _fixture("amazon_search_normal.json")
    listing = AmazonResponseParser().parse(payload, source_query="gucci")[0]
    profile = extract_from_listing(listing)

    assert listing.listing_id == listing.sku == "B0TEST1234"
    assert profile.listing_id == "B0TEST1234"
    sku_ids = [
        item.normalized_value
        for item in profile.structured_identifiers
        if item.identifier_type is IdentifierType.SKU
    ]
    assert sku_ids == ["B0TEST1234"]


def test_marketplace_search_result_parity() -> None:
    payload = _fixture("amazon_search_multiple.json")
    product = Product(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    legacy_marketplace = AmazonMarketplace(
        client=_legacy_client(handler),
        config=_config(use_transport=False),
    )
    transport_marketplace = AmazonMarketplace(
        client=_transport_client(handler),
        config=_config(use_transport=True),
    )

    legacy_result = legacy_marketplace.search(product)
    transport_result = transport_marketplace.search(product)

    assert legacy_result.status == transport_result.status
    assert legacy_result.total_results == transport_result.total_results == 3
    assert legacy_result.next_page_token == transport_result.next_page_token == "page-2-token"
    assert _listing_snapshots(legacy_result.listings) == _listing_snapshots(transport_result.listings)
    assert _listing_snapshots(legacy_result.valid_listings) == _listing_snapshots(
        transport_result.valid_listings
    )


def test_keyword_search_request_body_parity() -> None:
    legacy_body: dict[str, object] = {}
    transport_body: dict[str, object] = {}
    payload = _fixture("amazon_search_empty.json")

    def legacy_handler(request: httpx.Request) -> httpx.Response:
        legacy_body.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=payload)

    def transport_handler(request: httpx.Request) -> httpx.Response:
        transport_body.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=payload)

    _legacy_client(legacy_handler).search_items(query="gucci wallet", max_results=5)
    _transport_client(transport_handler).search_items(query="gucci wallet", max_results=5)

    assert legacy_body == transport_body
    assert legacy_body["Keywords"] == "gucci wallet"
    assert legacy_body["PartnerTag"] == PARTNER_TAG
    assert legacy_body["ItemCount"] == 5


def test_page_token_request_body_parity() -> None:
    legacy_body: dict[str, object] = {}
    transport_body: dict[str, object] = {}
    payload = _fixture("amazon_search_empty.json")

    def legacy_handler(request: httpx.Request) -> httpx.Response:
        legacy_body.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=payload)

    def transport_handler(request: httpx.Request) -> httpx.Response:
        transport_body.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=payload)

    _legacy_client(legacy_handler).search_items(query="bag", page=1, page_token="3")
    _transport_client(transport_handler).search_items(query="bag", page=1, page_token="3")

    assert legacy_body == transport_body
    assert legacy_body["ItemPage"] == 3


@pytest.mark.parametrize(
    "status,expected_type",
    [
        (400, AmazonClientError),
        (401, AmazonAuthenticationError),
        (403, AmazonAuthenticationError),
        (404, AmazonClientError),
        (429, AmazonRateLimitError),
        (500, AmazonServerError),
        (503, AmazonServerError),
    ],
)
def test_exception_type_parity(status: int, expected_type: type[AmazonMarketplaceError]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"Errors": []})

    legacy_exc: Exception | None = None
    transport_exc: Exception | None = None

    try:
        _legacy_client(handler).search_items(query="bag")
    except Exception as exc:
        legacy_exc = exc

    try:
        _transport_client(handler).search_items(query="bag")
    except Exception as exc:
        transport_exc = exc

    assert legacy_exc is not None
    assert transport_exc is not None
    assert type(legacy_exc) is expected_type
    assert type(transport_exc) is expected_type
    assert type(legacy_exc) is type(transport_exc)


def test_exception_parity_no_retry_when_retry_count_zero_for_429() -> None:
    def _make_handler() -> tuple[Callable[[httpx.Request], httpx.Response], dict[str, int]]:
        attempts = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(429, json={"Errors": []})

        return handler, attempts

    legacy_handler, legacy_attempts = _make_handler()
    transport_handler, transport_attempts = _make_handler()

    with pytest.raises(AmazonRateLimitError):
        _legacy_client(legacy_handler, retry_count=0).search_items(query="bag")
    with pytest.raises(AmazonRateLimitError):
        _transport_client(transport_handler, retry_count=0).search_items(query="bag")

    assert legacy_attempts["count"] == 1
    assert transport_attempts["count"] == 1


def test_signing_headers_generated_on_both_paths() -> None:
    legacy_headers: dict[str, str] = {}
    transport_headers: dict[str, str] = {}
    payload = _fixture("amazon_search_empty.json")

    def legacy_handler(request: httpx.Request) -> httpx.Response:
        legacy_headers.update(dict(request.headers))
        return httpx.Response(200, json=payload)

    def transport_handler(request: httpx.Request) -> httpx.Response:
        transport_headers.update(dict(request.headers))
        return httpx.Response(200, json=payload)

    _legacy_client(legacy_handler).search_items(query="bag")
    _transport_client(transport_handler).search_items(query="bag")

    for headers in (legacy_headers, transport_headers):
        assert headers["authorization"].startswith("AWS4-HMAC-SHA256")
        assert headers["x-amz-date"]
        assert headers["x-amz-target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"


def test_signing_secrets_not_logged(caplog) -> None:
    caplog.set_level(logging.INFO)
    payload = _fixture("amazon_search_empty.json")

    client = _transport_client(lambda r: httpx.Response(200, json=payload))
    client.search_items(query="bag")

    combined = caplog.text
    for record in caplog.records:
        combined += str(getattr(record, "transport", {}))
    assert SECRET_KEY not in combined
    assert ACCESS_KEY not in combined


def test_feature_flag_false_does_not_invoke_http_transport() -> None:
    payload = _fixture("amazon_search_empty.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _legacy_client(handler)
    with patch("utils.transport.HttpTransport.post", side_effect=AssertionError("transport must not run")):
        result = client.search_items(query="bag")

    assert result == payload


def test_feature_flag_true_invokes_http_transport() -> None:
    payload = _fixture("amazon_search_empty.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = _transport_client(handler)
    transport_calls: list[str] = []

    from utils.transport.transport import HttpTransport

    original_post = HttpTransport.post

    def _recording_post(self, url, **kwargs):
        transport_calls.append("called")
        return original_post(self, url, **kwargs)

    with patch.object(HttpTransport, "post", _recording_post):
        result = client.search_items(query="bag")

    assert result == payload
    assert transport_calls == ["called"]


def test_from_env_feature_flag_defaults_false(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.AMAZON_USE_TRANSPORT", False)
    config = AmazonConfig.from_env()
    assert config.use_transport is False


def test_from_env_feature_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.AMAZON_USE_TRANSPORT", True)
    config = AmazonConfig.from_env()
    assert config.use_transport is True
