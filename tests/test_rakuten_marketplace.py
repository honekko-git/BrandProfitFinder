"""Unit tests for marketplace.rakuten_marketplace."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from config.constants import MARKETPLACE_RAKUTEN
from marketplace.rakuten_client import FakeRakutenClient
from marketplace.rakuten_exceptions import RakutenResponseError
from marketplace.rakuten_marketplace import RakutenMarketplace
from marketplace.rakuten_response_parser import RakutenResponseParser
from marketplace.rakuten_settings import RakutenConfig
from models.marketplace_search_result import SEARCH_ERROR, SEARCH_NO_LISTINGS, SEARCH_SUCCESS
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"


def _config(**overrides) -> RakutenConfig:
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
    )
    defaults.update(overrides)
    return RakutenConfig(**defaults)


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _product(**kwargs) -> Product:
    defaults = dict(
        name="Gucci Marmont Wallet",
        brand="GUCCI",
        model="456126",
        sku="456126",
        price=600.0,
        currency="USD",
        exchange_rate=150.0,
    )
    defaults.update(kwargs)
    return Product(**defaults)


def _marketplace(name: str = "rakuten_search_multiple.json") -> RakutenMarketplace:
    return RakutenMarketplace(client=FakeRakutenClient(_payload(name)), config=_config())


def test_client_called_with_keyword() -> None:
    client = FakeRakutenClient(_payload("rakuten_search_normal.json"))
    RakutenMarketplace(client=client, config=_config()).search(_product())
    assert client.last_keyword == "GUCCI 456126"


def test_jan_search_priority() -> None:
    client = FakeRakutenClient(_payload("rakuten_search_empty.json"))
    RakutenMarketplace(client=client, config=_config()).search(_product(sku="4901234567890"))
    assert client.last_keyword == "4901234567890"


def test_query_override() -> None:
    client = FakeRakutenClient(_payload("rakuten_search_empty.json"))
    RakutenMarketplace(client=client, config=_config()).search(_product(), query="custom query")
    assert client.last_keyword == "custom query"


def test_empty_results() -> None:
    result = _marketplace("rakuten_search_empty.json").search(_product())
    assert result.status == SEARCH_NO_LISTINGS


def test_valid_results() -> None:
    result = _marketplace().search(_product())
    assert result.status == SEARCH_SUCCESS
    assert len(result.valid_listings) >= 2


def test_no_client_configured() -> None:
    result = RakutenMarketplace(client=None, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR
    assert "not configured" in (result.error_message or "")


def test_client_exception() -> None:
    class BrokenClient(FakeRakutenClient):
        def search_items(self, **kwargs):
            raise RuntimeError("client failure")

    result = RakutenMarketplace(client=BrokenClient({}), config=_config()).search(_product())
    assert result.status == SEARCH_ERROR


def test_parser_exception(monkeypatch) -> None:
    client = FakeRakutenClient({"Items": "bad"})

    def broken_validate(payload):
        raise RakutenResponseError("bad payload")

    monkeypatch.setattr(RakutenResponseParser, "validate_payload", staticmethod(broken_validate))
    result = RakutenMarketplace(client=client, config=_config()).search(_product())
    assert result.status == SEARCH_ERROR


def test_page_metadata() -> None:
    result = _marketplace().search(_product())
    assert result.total_results == 3
    assert result.next_page_token == "2"
    assert result.metadata.get("page_count") == 2


def test_hits_limit_passed() -> None:
    client = FakeRakutenClient(_payload("rakuten_search_empty.json"))
    RakutenMarketplace(client=client, config=_config(hits=10)).search(_product())
    assert client.last_hits == 10


def test_product_not_mutated() -> None:
    product = _product()
    original = deepcopy(product)
    _marketplace().search(product)
    assert product == original


def test_marketplace_name() -> None:
    result = _marketplace().search(_product())
    assert result.marketplace_name == MARKETPLACE_RAKUTEN
