"""Unit tests for marketplace.amazon_api_client."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import AmazonClientProtocol, FakeAmazonClient
from marketplace.amazon_exceptions import (
    AmazonApiError,
    AmazonAuthenticationError,
    AmazonConfigurationError,
    AmazonClientError,
    AmazonRateLimitError,
    AmazonServerError,
)
from marketplace.amazon_settings import AmazonConfig

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "super-secret-amazon-secret-key"
ACCESS_KEY = "AKIA_TEST_ACCESS_KEY"
PARTNER_TAG = "partner-tag-001"


def _config(**overrides) -> AmazonConfig:
    defaults = dict(
        marketplace_id="A1VC38T7YXB528",
        default_currency="JPY",
        default_language="ja_JP",
        max_results=20,
        timeout_seconds=10,
        retry_count=0,
        enabled=True,
        demo_enabled=False,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        partner_tag=PARTNER_TAG,
        region="us-west-2",
        api_host="webservices.amazon.co.jp",
        use_transport=False,
    )
    defaults.update(overrides)
    return AmazonConfig(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_client_creation_from_settings() -> None:
    client = AmazonApiClient.from_settings(_config())
    assert client.config.partner_tag == PARTNER_TAG


def test_protocol_compatibility() -> None:
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(200, json=raw)),
    )
    assert isinstance(client, AmazonClientProtocol)


def test_fake_client_unchanged() -> None:
    payload = {"items": [], "total_results": 0, "next_page_token": None}
    fake = FakeAmazonClient(payload)
    result = fake.search_items(query="bag")
    assert result == payload
    assert fake.last_query == "bag"


def test_missing_query_raises() -> None:
    client = AmazonApiClient(config=_config())
    with pytest.raises(ValueError, match="query is required"):
        client.search_items(query="  ")


def test_missing_credentials_raises() -> None:
    client = AmazonApiClient(config=_config(access_key="", secret_key="", partner_tag=""))
    with pytest.raises(AmazonConfigurationError, match="credentials are not configured"):
        client.search_items(query="bag")


def test_request_construction_posts_signed_payload() -> None:
    captured: dict[str, object] = {}
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=raw)

    client = AmazonApiClient(config=_config(use_transport=False), client=_mock_client(handler))
    payload = client.search_items(query="gucci wallet", max_results=5, page_token="2")

    assert captured["method"] == "POST"
    assert captured["url"] == "https://webservices.amazon.co.jp/paapi5/searchitems"
    assert captured["body"]["Keywords"] == "gucci wallet"
    assert captured["body"]["PartnerTag"] == PARTNER_TAG
    assert captured["body"]["ItemCount"] == 5
    assert captured["body"]["ItemPage"] == 2
    assert "authorization" in {key.lower() for key in captured["headers"]}
    assert payload["items"][0]["asin"] == "B0TEST1234"
    assert payload["total_results"] == 3


def test_http_429_raises_rate_limit_error() -> None:
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(429, json={"Errors": []})),
    )
    with pytest.raises(AmazonRateLimitError):
        client.search_items(query="bag")


def test_http_403_raises_authentication_error() -> None:
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(403, json={"Errors": []})),
    )
    with pytest.raises(AmazonAuthenticationError):
        client.search_items(query="bag")


def test_http_400_raises_client_error() -> None:
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(400, json={"Errors": []})),
    )
    with pytest.raises(AmazonClientError):
        client.search_items(query="bag")


def test_http_500_raises_server_error() -> None:
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(500, json={"Errors": []})),
    )
    with pytest.raises(AmazonServerError):
        client.search_items(query="bag")


def test_timeout_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = AmazonApiClient(config=_config(), client=_mock_client(handler))
    with pytest.raises(AmazonApiError, match="timed out"):
        client.search_items(query="bag")


def test_secrets_not_in_exception_messages() -> None:
    client = AmazonApiClient(
        config=_config(),
        client=_mock_client(lambda r: httpx.Response(403, json={"Errors": []})),
    )
    with pytest.raises(AmazonAuthenticationError) as exc_info:
        client.search_items(query="bag")
    assert SECRET_KEY not in str(exc_info.value)
    assert ACCESS_KEY not in str(exc_info.value)


def test_mask_signed_headers_for_log() -> None:
    masked = AmazonApiClient.mask_signed_headers_for_log(
        {"Authorization": f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/scope, Signature=abc"}
    )
    assert ACCESS_KEY not in masked["Authorization"]
