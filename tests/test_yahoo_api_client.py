"""Unit tests for marketplace.yahoo_api_client."""

import json
from pathlib import Path

import httpx
import pytest

from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_exceptions import (
    YahooClientError,
    YahooConfigError,
    YahooRateLimitError,
    YahooResponseError,
    YahooServerError,
)
from marketplace.yahoo_settings import YahooApiSettings

FIXTURES = Path(__file__).parent / "fixtures"
DUMMY_CLIENT_ID = "dummy-test-client-id"


def _settings(**overrides) -> YahooApiSettings:
    defaults = dict(
        client_id=DUMMY_CLIENT_ID,
        base_url="https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
        timeout_seconds=10,
        results=20,
        enabled=True,
    )
    defaults.update(overrides)
    return YahooApiSettings(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_query_search_params() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))
        return httpx.Response(200, json=payload)

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    client.search_items(query="gucci bag")

    assert captured["params"]["query"] == "gucci bag"
    assert "jan_code" not in captured["params"]


def test_jan_code_search_params() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    client.search_items(jan_code="4901234567890")

    assert captured["params"]["jan_code"] == "4901234567890"


def test_appid_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    client.search_items(query="bag")

    assert captured["params"]["appid"] == DUMMY_CLIENT_ID


def test_results_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(results=15), client=_mock_client(handler))
    client.search_items(query="bag", results=5)

    assert captured["params"]["results"] == "5"


def test_start_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    client.search_items(query="bag", start=3)

    assert captured["params"]["start"] == "3"


def test_in_stock_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"hits": []})

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    client.search_items(query="bag", in_stock=True)

    assert captured["params"]["in_stock"] == "true"


def test_missing_query_and_jan_raises() -> None:
    client = YahooApiClient(settings=_settings(), client=_mock_client(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ValueError, match="query or jan_code is required"):
        client.search_items()


def test_missing_client_id_raises() -> None:
    client = YahooApiClient(settings=_settings(client_id=""), client=_mock_client(lambda r: httpx.Response(200, json={})))
    with pytest.raises(YahooConfigError, match="Client ID is not configured"):
        client.search_items(query="bag")


def test_http_success() -> None:
    payload = json.loads((FIXTURES / "yahoo_item_search_success.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    result = client.search_items(query="gucci")
    assert isinstance(result, dict)
    assert len(result["hits"]) >= 3


@pytest.mark.parametrize("status,exc_type", [(400, YahooClientError), (403, YahooClientError)])
def test_http_client_errors(status: int, exc_type) -> None:
    client = YahooApiClient(
        settings=_settings(),
        client=_mock_client(lambda r: httpx.Response(status, json={"error": "bad"})),
    )
    with pytest.raises(exc_type):
        client.search_items(query="bag")


def test_http_429() -> None:
    client = YahooApiClient(
        settings=_settings(),
        client=_mock_client(lambda r: httpx.Response(429, json={"error": "rate limit"})),
    )
    with pytest.raises(YahooRateLimitError):
        client.search_items(query="bag")


def test_http_500() -> None:
    client = YahooApiClient(
        settings=_settings(),
        client=_mock_client(lambda r: httpx.Response(500, json={"error": "server"})),
    )
    with pytest.raises(YahooServerError):
        client.search_items(query="bag")


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    with pytest.raises(Exception, match="timed out"):
        client.search_items(query="bag")


def test_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = YahooApiClient(settings=_settings(), client=_mock_client(handler))
    with pytest.raises(Exception, match="connection error"):
        client.search_items(query="bag")


def test_json_decode_error() -> None:
    client = YahooApiClient(
        settings=_settings(),
        client=_mock_client(lambda r: httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"})),
    )
    with pytest.raises(YahooResponseError, match="invalid JSON"):
        client.search_items(query="bag")


def test_client_id_not_in_exception_message() -> None:
    secret = "super-secret-yahoo-client-id"
    client = YahooApiClient(settings=_settings(client_id=secret), client=_mock_client(lambda r: httpx.Response(403, json={})))
    with pytest.raises(YahooClientError) as exc_info:
        client.search_items(query="bag")
    assert secret not in str(exc_info.value)


def test_mask_params_for_log() -> None:
    masked = YahooApiClient.mask_params_for_log({"appid": "secret", "query": "bag"})
    assert "secret" not in masked
    assert "appid=%2A%2A%2A" in masked or "appid=***" in masked


def test_no_real_network() -> None:
    client = YahooApiClient(
        settings=_settings(),
        client=_mock_client(lambda r: httpx.Response(200, json={"hits": []})),
    )
    result = client.search_items(query="bag")
    assert result == {"hits": []}
