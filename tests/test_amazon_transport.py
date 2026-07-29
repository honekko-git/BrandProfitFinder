"""Integration tests for Amazon client Version 2 transport migration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_exceptions import (
    AmazonApiError,
    AmazonRateLimitError,
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


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


def test_feature_flag_disabled_uses_legacy_httpx_path() -> None:
    captured: dict[str, object] = {}
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        return httpx.Response(200, json=raw)

    client = AmazonApiClient(
        config=_config(use_transport=False),
        client=_mock_client(handler),
    )
    payload = client.search_items(query="bag")

    assert captured["method"] == "POST"
    assert payload["items"][0]["asin"] == "B0TEST1234"


def test_feature_flag_enabled_successful_search() -> None:
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=raw)

    client = AmazonApiClient(
        config=_config(use_transport=True),
        client=_mock_client(handler),
    )
    payload = client.search_items(query="gucci wallet")

    assert len(payload["items"]) == 2
    assert payload["total_results"] == 3


def test_feature_flag_enabled_uses_http_transport() -> None:
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))

    with patch("utils.transport.transport.HttpTransport.post") as mock_post:
        mock_post.return_value = _transport_response(raw)
        client = AmazonApiClient(config=_config(use_transport=True))
        payload = client.search_items(query="bag")

    assert payload["items"][0]["asin"] == "B0TEST1234"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256")


def test_feature_flag_enabled_429_no_retry_when_retry_count_zero() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"Errors": []})

    client = AmazonApiClient(
        config=_config(use_transport=True, retry_count=0),
        client=_mock_client(handler),
    )
    with pytest.raises(AmazonRateLimitError):
        client.search_items(query="bag")

    assert attempts["count"] == 1


def test_feature_flag_enabled_timeout_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = AmazonApiClient(
        config=_config(use_transport=True, retry_count=0),
        client=_mock_client(handler),
    )
    with pytest.raises(AmazonApiError, match="timed out"):
        client.search_items(query="bag")


def test_feature_flag_enabled_no_secret_logging(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")
    raw = json.loads((FIXTURES / "amazon_paapi_search_raw.json").read_text(encoding="utf-8"))

    client = AmazonApiClient(
        config=_config(use_transport=True),
        client=_mock_client(lambda r: httpx.Response(200, json=raw)),
    )
    client.search_items(query="bag")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))
    assert SECRET_KEY not in combined
    assert ACCESS_KEY not in combined


def _transport_response(raw: dict):
    from utils.transport.models import TransportResponse

    return TransportResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(raw).encode("utf-8"),
        elapsed_seconds=0.01,
        retry_count=0,
    )


def test_use_transport_defaults_false_from_config_helper() -> None:
    assert _config().use_transport is False


def test_retry_count_defaults_zero_from_config_helper() -> None:
    assert _config().retry_count == 0
