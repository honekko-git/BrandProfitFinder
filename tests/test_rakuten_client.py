"""Unit tests for marketplace.rakuten_client."""

import json
from pathlib import Path

import httpx
import pytest

from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient
from marketplace.rakuten_exceptions import (
    RakutenClientError,
    RakutenConfigError,
    RakutenNotFoundError,
    RakutenRateLimitError,
    RakutenResponseError,
    RakutenServerError,
    RakutenServiceUnavailableError,
)
from marketplace.rakuten_settings import RakutenConfig

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "super-secret-rakuten-access-key"


def _config(**overrides) -> RakutenConfig:
    defaults = dict(
        application_id="dummy-app-id",
        access_key=SECRET_KEY,
        affiliate_id="",
        base_url="https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_successful_request_params() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        payload = json.loads((FIXTURES / "rakuten_search_normal.json").read_text(encoding="utf-8"))
        return httpx.Response(200, json=payload)

    client = RakutenApiClient(settings=_config(), client=_mock_client(handler))
    client.search_items(keyword="gucci wallet")

    assert captured["params"]["applicationId"] == "dummy-app-id"
    assert captured["params"]["format"] == "json"
    assert captured["params"]["formatVersion"] == "2"
    assert captured["params"]["keyword"] == "gucci wallet"
    assert captured["params"]["hits"] == "20"
    assert captured["params"]["page"] == "1"
    assert captured["params"]["sort"] == "standard"
    assert "affiliateId" not in captured["params"]


def test_access_key_in_header_not_params() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(settings=_config(), client=_mock_client(handler))
    client.search_items(keyword="bag")

    assert SECRET_KEY not in str(captured["params"])
    assert captured["headers"]["authorization"] == f"Bearer {SECRET_KEY}"


def test_affiliate_id_optional() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(settings=_config(affiliate_id="aff-123"), client=_mock_client(handler))
    client.search_items(keyword="bag")
    assert captured["params"]["affiliateId"] == "aff-123"


def test_missing_credentials_raises() -> None:
    client = RakutenApiClient(settings=_config(application_id=""), client=_mock_client(lambda r: httpx.Response(200, json={})))
    with pytest.raises(RakutenConfigError):
        client.search_items(keyword="bag")


def test_empty_keyword_raises() -> None:
    client = RakutenApiClient(settings=_config(), client=_mock_client(lambda r: httpx.Response(200, json={})))
    with pytest.raises(ValueError, match="keyword is required"):
        client.search_items(keyword="")


@pytest.mark.parametrize(
    "status,exc_type",
    [
        (400, RakutenClientError),
        (429, RakutenRateLimitError),
        (500, RakutenServerError),
        (503, RakutenServiceUnavailableError),
    ],
)
def test_http_errors(status: int, exc_type) -> None:
    client = RakutenApiClient(
        settings=_config(),
        client=_mock_client(lambda r: httpx.Response(status, json={"error": "fail"})),
    )
    with pytest.raises(exc_type):
        client.search_items(keyword="bag")


def test_http_404_raises_not_found() -> None:
    client = RakutenApiClient(
        settings=_config(),
        client=_mock_client(lambda r: httpx.Response(404, json={"error": "not found"})),
    )
    with pytest.raises(RakutenNotFoundError):
        client.search_items(keyword="bag")


def test_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = RakutenApiClient(settings=_config(), client=_mock_client(handler))
    with pytest.raises(Exception, match="timed out"):
        client.search_items(keyword="bag")


def test_invalid_json() -> None:
    client = RakutenApiClient(
        settings=_config(),
        client=_mock_client(lambda r: httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"})),
    )
    with pytest.raises(RakutenResponseError):
        client.search_items(keyword="bag")


def test_credentials_not_in_exception() -> None:
    client = RakutenApiClient(settings=_config(), client=_mock_client(lambda r: httpx.Response(403, json={})))
    with pytest.raises(Exception) as exc_info:
        client.search_items(keyword="bag")
    assert SECRET_KEY not in str(exc_info.value)


def test_mask_headers_for_log() -> None:
    masked = RakutenApiClient.mask_headers_for_log({"Authorization": f"Bearer {SECRET_KEY}"})
    assert SECRET_KEY not in masked["Authorization"]


def test_fake_client_records_calls() -> None:
    fake = FakeRakutenClient({"Items": []})
    fake.search_items(keyword="gucci", hits=5, page=2, sort="+itemPrice")
    assert fake.last_keyword == "gucci"
    assert fake.last_hits == 5
    assert fake.last_page == 2
    assert fake.last_sort == "+itemPrice"


def test_no_real_network() -> None:
    fake = FakeRakutenClient({"Items": []})
    result = RakutenApiClient(settings=_config(), client=_mock_client(lambda r: httpx.Response(200, json={"Items": []})))
    payload = result.search_items(keyword="bag")
    assert payload == {"Items": []}
