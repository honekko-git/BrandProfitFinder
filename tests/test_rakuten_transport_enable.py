"""Production-readiness validation for Rakuten with RAKUTEN_USE_TRANSPORT enabled."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from config import settings
from marketplace.marketplace_factory import create_marketplace
from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient
from marketplace.rakuten_marketplace import RakutenMarketplace, create_rakuten_marketplace
from marketplace.rakuten_response_parser import RakutenResponseParser
from marketplace.rakuten_settings import RakutenConfig
from models.marketplace_search_result import SEARCH_SUCCESS
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_KEY = "live-validation-access-key"


def _transport_config(**overrides) -> RakutenConfig:
    defaults = dict(
        application_id="dummy-app-id",
        access_key=SECRET_KEY,
        affiliate_id="aff-123",
        base_url="https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
        timeout_seconds=10,
        max_retries=0,
        hits=20,
        sort="standard",
        enabled=True,
        demo_enabled=False,
        use_transport=True,
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


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
    monkeypatch.setenv("RAKUTEN_USE_TRANSPORT", "true")
    monkeypatch.setattr(settings, "RAKUTEN_USE_TRANSPORT", True)

    config = RakutenConfig.from_env()

    assert config.use_transport is True


def test_environment_flag_loads_use_transport_false_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RAKUTEN_USE_TRANSPORT", raising=False)
    monkeypatch.setattr(settings, "RAKUTEN_USE_TRANSPORT", False)

    config = RakutenConfig.from_env()

    assert config.use_transport is False


def test_factory_flow_uses_transport_enabled_api_client() -> None:
    payload = json.loads((FIXTURES / "rakuten_search_normal.json").read_text(encoding="utf-8"))
    transport_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    api_client = RakutenApiClient(settings=config, client=_mock_client(handler))
    marketplace = create_marketplace(
        "rakuten",
        rakuten_settings=config,
        rakuten_client=api_client,
    )

    assert isinstance(marketplace, RakutenMarketplace)
    assert marketplace.config.use_transport is True
    assert isinstance(marketplace._client, RakutenApiClient)

    from utils.transport.transport import HttpTransport

    original_get = HttpTransport.get

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return original_get(self, url, **kwargs)

    with patch.object(HttpTransport, "get", _recording_get):
        result = marketplace.search(_product())

    assert transport_calls == ["called"]
    assert result.status == SEARCH_SUCCESS
    assert result.selected_listing is not None


def test_create_rakuten_marketplace_factory_helper_with_transport_client() -> None:
    config = _transport_config()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Items": []})

    client = RakutenApiClient(settings=config, client=_mock_client(handler))
    marketplace = create_rakuten_marketplace(client=client, config=config)

    assert marketplace.config.use_transport is True
    assert marketplace._client is client


def test_search_pipeline_transport_parser_and_result_metadata() -> None:
    payload = json.loads((FIXTURES / "rakuten_search_multiple.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = RakutenMarketplace(
        client=RakutenApiClient(settings=config, client=_mock_client(handler)),
        config=config,
    )

    result = marketplace.search(_product())
    parser = RakutenResponseParser()
    meta = parser.parse_metadata(payload)

    assert result.status == SEARCH_SUCCESS
    assert result.total_results == meta["count"] == 3
    assert result.metadata["page"] == meta["page"] == 1
    assert result.metadata["page_count"] == meta["page_count"] == 2
    assert result.metadata["has_next_page"] is True
    assert len(result.listings) == 3
    assert len(result.valid_listings) >= 1
    assert result.listings[0].title
    assert result.listings[0].price_jpy is not None
    assert result.listings[0].listing_url.startswith("https://")


def test_fake_rakuten_client_regression_unchanged_with_transport_config_enabled() -> None:
    payload = json.loads((FIXTURES / "rakuten_search_normal.json").read_text(encoding="utf-8"))
    fake = FakeRakutenClient(payload)
    config = _transport_config()

    marketplace = RakutenMarketplace(client=fake, config=config)
    result = marketplace.search(_product())

    assert fake.last_keyword == "GUCCI 456126"
    assert result.status == SEARCH_SUCCESS
    assert len(result.valid_listings) >= 1

    direct = fake.search_items(keyword="manual-query", hits=5, page=2, sort="+itemPrice")
    assert direct == payload
    assert fake.last_keyword == "manual-query"
    assert fake.last_hits == 5
    assert fake.last_page == 2
    assert fake.last_sort == "+itemPrice"


def test_logging_security_transport_enabled_full_pipeline(caplog) -> None:
    caplog.set_level(logging.INFO)

    payload = json.loads((FIXTURES / "rakuten_search_normal.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = _transport_config()
    marketplace = RakutenMarketplace(
        client=RakutenApiClient(settings=config, client=_mock_client(handler)),
        config=config,
    )
    marketplace.search(_product())

    transport_records = [
        record for record in caplog.records if record.name == "utils.transport.logging_utils"
    ]
    assert transport_records
    combined = "\n".join(record.getMessage() for record in transport_records)
    for record in transport_records:
        combined += str(getattr(record, "transport", {}))

    assert SECRET_KEY not in combined
    assert f"Bearer {SECRET_KEY}" not in combined
