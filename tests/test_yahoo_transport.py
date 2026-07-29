"""Integration tests for Yahoo client Version 2 transport migration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_exceptions import (
    YahooApiError,
    YahooClientError,
    YahooRateLimitError,
    YahooServerError,
)
from marketplace.yahoo_settings import YahooApiSettings

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_CLIENT_ID = "super-secret-yahoo-client-id"


def _settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id=SECRET_CLIENT_ID,
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
        use_transport=False,
        max_retries=0,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


def test_feature_flag_disabled_uses_legacy_httpx_path() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(
        settings=_settings(use_transport=False, max_retries=0),
        client=_mock_client(handler),
    )
    payload = client.search_items(query="bag")

    assert payload == {"hits": []}
    assert captured["method"] == "GET"


def test_feature_flag_enabled_successful_search() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))
        return httpx.Response(200, json=payload)

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    payload = client.search_items(query="gucci bag")

    assert captured["params"]["query"] == "gucci bag"
    assert captured["params"]["appid"] == SECRET_CLIENT_ID
    assert isinstance(payload["hits"], list)
    assert len(payload["hits"]) >= 3


def test_feature_flag_enabled_uses_http_transport() -> None:
    from utils.transport.models import TransportResponse

    with patch("utils.transport.transport.HttpTransport.get") as mock_get:
        mock_get.return_value = TransportResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"hits": []}',
            elapsed_seconds=0.01,
            retry_count=0,
        )
        client = YahooApiClient(settings=_settings(use_transport=True, max_retries=0))
        payload = client.search_items(query="bag")

    assert payload == {"hits": []}
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args.kwargs
    assert call_kwargs["params"]["query"] == "bag"
    assert call_kwargs["params"]["appid"] == SECRET_CLIENT_ID


def test_feature_flag_enabled_jan_code_search() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    client.search_items(jan_code="4901234567890")

    assert captured["params"]["jan_code"] == "4901234567890"


def test_feature_flag_enabled_429_no_retry_when_max_retries_zero() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(429, json={"error": "rate limit"})

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    with pytest.raises(YahooRateLimitError):
        client.search_items(query="bag")

    assert attempts["count"] == 1


def test_feature_flag_enabled_429_retries_when_max_retries_increased() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, json={"error": "rate limit"})
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=2),
        client=_mock_client(handler),
    )
    payload = client.search_items(query="bag")

    assert payload == {"hits": []}
    assert attempts["count"] == 2


def test_feature_flag_enabled_404_maps_to_client_error() -> None:
    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(404, json={"error": "not found"})),
    )
    with pytest.raises(YahooClientError, match="HTTP 404"):
        client.search_items(query="bag")


def test_feature_flag_enabled_401_maps_to_client_error_without_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=3),
        client=_mock_client(handler),
    )
    with pytest.raises(YahooClientError):
        client.search_items(query="bag")

    assert attempts["count"] == 1


def test_feature_flag_enabled_403_maps_to_client_error_without_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=3),
        client=_mock_client(handler),
    )
    with pytest.raises(YahooClientError) as exc_info:
        client.search_items(query="bag")

    assert attempts["count"] == 1
    assert SECRET_CLIENT_ID not in str(exc_info.value)


def test_feature_flag_enabled_400_maps_to_client_error() -> None:
    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(400, json={"error": "bad"})),
    )
    with pytest.raises(YahooClientError):
        client.search_items(query="bag")


def test_feature_flag_enabled_500_maps_to_server_error() -> None:
    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(500, json={"error": "server"})),
    )
    with pytest.raises(YahooServerError):
        client.search_items(query="bag")


def test_feature_flag_enabled_503_maps_to_server_error() -> None:
    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(503, json={"error": "unavailable"})),
    )
    with pytest.raises(YahooServerError):
        client.search_items(query="bag")


def test_feature_flag_enabled_timeout_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    with pytest.raises(YahooApiError, match="timed out"):
        client.search_items(query="bag")


def test_feature_flag_enabled_connection_error_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    with pytest.raises(YahooApiError, match="connection error"):
        client.search_items(query="bag")


def test_feature_flag_enabled_no_appid_logging(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")

    client = YahooApiClient(
        settings=_settings(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(200, json={"hits": []})),
    )
    client.search_items(query="bag")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))
    assert SECRET_CLIENT_ID not in combined


def test_use_transport_defaults_false_from_settings_helper() -> None:
    assert _settings().use_transport is False


def test_max_retries_defaults_zero_from_settings_helper() -> None:
    assert _settings().max_retries == 0


def test_max_retries_zero_from_env(monkeypatch) -> None:
    monkeypatch.setattr("config.settings.YAHOO_API_MAX_RETRIES", 0)
    settings = YahooApiSettings.from_env()
    assert settings.max_retries == 0
