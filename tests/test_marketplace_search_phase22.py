"""Phase 22: marketplace search framework."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.constants import MARKETPLACE_STOCKX
from marketplace.goat_marketplace import GoatMarketplace
from marketplace.stockx_client import FakeStockXClient
from marketplace.stockx_marketplace import StockXMarketplace
from marketplace.stockx_settings import StockXSettings
from marketplace_search.capability import MarketplaceCapability
from marketplace_search.models import SearchRequest, SearchResult
from marketplace_search.policy import SearchPolicy
from marketplace_search.service import MarketplaceSearchService
from models.marketplace_search_result import SEARCH_ERROR, SEARCH_SUCCESS
from models.product import Product

FIXTURES = Path(__file__).parent / "fixtures"


def _settings(**overrides) -> StockXSettings:
    defaults = dict(
        enabled=True,
        timeout_seconds=10,
        page_size=20,
        max_pages=2,
        default_currency="JPY",
        demo_fixture_path="stockx_search_normal.json",
        allow_unknown_currency=False,
        include_unavailable=False,
        include_sold=False,
        include_inactive=False,
        include_new=True,
        include_preowned=False,
        include_low_liquidity=True,
        require_known_lowest_ask=True,
        require_known_shipping=False,
        require_known_fees=False,
        minimum_sales_last_30_days=0,
        minimum_asks_count=0,
        minimum_bids_count=0,
        maximum_volatility_rate=None,
        preferred_price_source="LOWEST_ASK",
    )
    defaults.update(overrides)
    return StockXSettings(**defaults)


def _stockx_marketplace(name: str = "stockx_search_normal.json") -> StockXMarketplace:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return StockXMarketplace(client=FakeStockXClient(payload), settings=_settings())


def _product() -> Product:
    return Product(
        name="Dunk Low",
        brand="NIKE",
        model="DD1391-100",
        sku="DD1391-100",
        price=120.0,
        currency="USD",
        exchange_rate=150.0,
    )


def test_search_request_from_product() -> None:
    product = _product()
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    assert request.marketplace_id == MARKETPLACE_STOCKX
    assert request.resolved_query() == "DD1391-100"


def test_search_policy_rejects_missing_marketplace_id() -> None:
    product = _product()
    request = SearchRequest(product=product, marketplace_id="")
    capability = MarketplaceCapability(marketplace_id="")
    result = SearchPolicy().validate(request, capability)
    assert result.valid is False
    assert any("marketplace_id" in error for error in result.errors)


def test_search_policy_rejects_marketplace_mismatch() -> None:
    product = _product()
    request = SearchRequest.from_product(product, "goat")
    capability = MarketplaceCapability(marketplace_id="stockx")
    result = SearchPolicy().validate(request, capability)
    assert result.valid is False
    assert any("mismatch" in error for error in result.errors)


def test_search_policy_rejects_empty_search_criteria() -> None:
    product = Product(name="", brand="", model="", sku="")
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    capability = MarketplaceCapability(marketplace_id=MARKETPLACE_STOCKX)
    result = SearchPolicy().validate(request, capability)
    assert result.valid is False
    assert any("query" in error for error in result.errors)


def test_marketplace_capability_from_stockx_adapter() -> None:
    adapter = _stockx_marketplace()
    capability = adapter.capability
    assert capability.marketplace_id == MARKETPLACE_STOCKX
    assert capability.supports_jan_search is True
    assert capability.supports_structured_identifiers is True
    assert capability.uses_fixture_data is False
    assert capability.requires_configured_client is False


def test_marketplace_capability_fixture_mode_without_client() -> None:
    adapter = StockXMarketplace()
    capability = adapter.capability
    assert capability.uses_fixture_data is True
    assert capability.requires_configured_client is True


def test_marketplace_search_service_routes_through_adapter() -> None:
    adapter = _stockx_marketplace()
    product = _product()
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    service = MarketplaceSearchService()
    direct = adapter.search(product)
    routed = service.search(adapter, request)
    assert isinstance(routed, SearchResult)
    assert routed.status == direct.status == SEARCH_SUCCESS
    assert routed.marketplace_result.listing_count == direct.listing_count
    assert routed.marketplace_result.selected_price_jpy == direct.selected_price_jpy


def test_marketplace_search_service_validation_error_skips_adapter_call() -> None:
    adapter = MagicMock(spec=StockXMarketplace)
    adapter.adapter_id = MARKETPLACE_STOCKX
    adapter.marketplace_name = MARKETPLACE_STOCKX
    adapter.adapter_version = "1.0"
    adapter.uses_fixture_data = False
    adapter.supports_structured_identifiers = True
    adapter.capability = MarketplaceCapability(marketplace_id=MARKETPLACE_STOCKX)
    product = Product(name="", brand="", model="", sku="")
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    result = MarketplaceSearchService().search(adapter, request)
    adapter.search.assert_not_called()
    assert result.status == SEARCH_ERROR


def test_deterministic_repeated_search() -> None:
    adapter = _stockx_marketplace()
    product = _product()
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    service = MarketplaceSearchService()
    first = service.search(adapter, request)
    second = service.search(adapter, request)
    assert first.status == second.status
    assert first.marketplace_result.selected_price_jpy == second.marketplace_result.selected_price_jpy
    assert first.marketplace_result.listing_count == second.marketplace_result.listing_count


def test_search_result_legacy_conversion() -> None:
    adapter = _stockx_marketplace()
    product = _product()
    request = SearchRequest.from_product(product, MARKETPLACE_STOCKX)
    result = MarketplaceSearchService().search(adapter, request)
    legacy = result.to_marketplace_search_result()
    assert legacy.marketplace_name == MARKETPLACE_STOCKX
    assert legacy.product is product


def test_goat_adapter_capability_and_search_service() -> None:
    from marketplace.goat_client import FakeGoatClient

    payload = json.loads((FIXTURES / "goat_search_normal.json").read_text(encoding="utf-8"))
    adapter = GoatMarketplace(client=FakeGoatClient(payload))
    product = _product()
    capability = adapter.capability
    assert capability.marketplace_id == "goat"
    assert capability.supports_jan_search is True
    result = MarketplaceSearchService().search(
        adapter,
        SearchRequest.from_product(product, "goat"),
    )
    assert result.status == SEARCH_SUCCESS
