"""Integration tests for Rakuten client Version 2 transport migration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pytest

from marketplace.rakuten_client import RakutenApiClient
from marketplace.rakuten_exceptions import (
    RakutenApiError,
    RakutenClientError,
    RakutenNotFoundError,
    RakutenRateLimitError,
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
        max_retries=2,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
        use_transport=False,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


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
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(
        settings=_config(use_transport=False, max_retries=0),
        client=_mock_client(handler),
    )
    payload = client.search_items(keyword="bag")

    assert payload == {"Items": []}
    assert captured["method"] == "GET"


def test_feature_flag_enabled_successful_search() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["headers"] = dict(request.headers)
        payload = json.loads((FIXTURES / "rakuten_search_normal.json").read_text(encoding="utf-8"))
        return httpx.Response(200, json=payload)

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=0),
        client=_mock_client(handler),
    )
    payload = client.search_items(keyword="gucci wallet")

    assert captured["params"]["keyword"] == "gucci wallet"
    assert captured["headers"]["authorization"] == f"Bearer {SECRET_KEY}"
    assert "Items" in payload


def test_feature_flag_enabled_429_retry_then_success() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, json={"error": "rate limit"})
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=2),
        client=_mock_client(handler),
    )
    payload = client.search_items(keyword="bag")

    assert payload == {"Items": []}
    assert attempts["count"] == 2


def test_feature_flag_enabled_503_retry_exhaustion() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=2),
        client=_mock_client(handler),
    )
    with pytest.raises(RakutenServiceUnavailableError):
        client.search_items(keyword="bag")

    assert attempts["count"] == 3


def test_feature_flag_enabled_503_exhaustion_maps_server_error_when_not_503_specific() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(500, json={"error": "server"})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=1),
        client=_mock_client(handler),
    )
    with pytest.raises(RakutenServerError):
        client.search_items(keyword="bag")

    assert attempts["count"] == 2


def test_feature_flag_enabled_404_maps_to_not_found() -> None:
    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(404, json={"error": "not found"})),
    )
    with pytest.raises(RakutenNotFoundError):
        client.search_items(keyword="bag")


def test_feature_flag_enabled_401_maps_to_api_error_without_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=3),
        client=_mock_client(handler),
    )
    with pytest.raises(RakutenApiError):
        client.search_items(keyword="bag")

    assert attempts["count"] == 1


def test_feature_flag_enabled_403_maps_to_api_error_without_retry() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=3),
        client=_mock_client(handler),
    )
    with pytest.raises(RakutenApiError) as exc_info:
        client.search_items(keyword="bag")

    assert attempts["count"] == 1
    assert SECRET_KEY not in str(exc_info.value)


def test_feature_flag_enabled_timeout_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.TimeoutException("timeout")
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=2),
        client=_mock_client(handler),
    )
    payload = client.search_items(keyword="bag")

    assert payload == {"Items": []}
    assert attempts["count"] == 2


def test_feature_flag_enabled_timeout_exhaustion_maps_to_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=1),
        client=_mock_client(handler),
    )
    with pytest.raises(RakutenApiError, match="timed out"):
        client.search_items(keyword="bag")


def test_feature_flag_enabled_400_maps_to_client_error() -> None:
    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(400, json={"error": "bad"})),
    )
    with pytest.raises(RakutenClientError):
        client.search_items(keyword="bag")


def test_feature_flag_enabled_no_secret_logging(caplog) -> None:
    caplog.set_level(logging.INFO, logger="utils.transport.logging_utils")

    client = RakutenApiClient(
        settings=_config(use_transport=True, max_retries=0),
        client=_mock_client(lambda r: httpx.Response(200, json={"Items": []})),
    )
    client.search_items(keyword="bag")

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))
    assert SECRET_KEY not in combined


def test_use_transport_defaults_false_from_config_helper() -> None:
    assert _config().use_transport is False
