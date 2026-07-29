"""Tests for live supplier fallback and pipeline compatibility."""

from __future__ import annotations

import pytest

from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from supplier.factory import _REGISTRY, _register_default_suppliers, create_supplier_client
from supplier.fashionphile.client import FashionphileClient
from supplier.live.resolver import LiveSupplierResolver, _LIVE_REGISTRY, register_live_supplier_client
from supplier.models import SupplierType


@pytest.fixture(autouse=True)
def restore_supplier_registries() -> None:
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()
    yield
    _REGISTRY.clear()
    _register_default_suppliers()
    _LIVE_REGISTRY.clear()


def test_live_resolver_fixture_fallback_matches_factory_client() -> None:
    factory_client = create_supplier_client("fashionphile")
    resolved = LiveSupplierResolver().resolve("fashionphile").client

    assert factory_client is not None
    assert resolved is not None
    assert resolved.supplier_name == factory_client.supplier_name


def test_live_registered_client_takes_priority_over_fixture() -> None:
    class _LiveFashionphileClient:
        @property
        def supplier_name(self) -> str:
            return "fashionphile"

        @property
        def supplier_type(self) -> SupplierType:
            return SupplierType.USED

        def search_products(self, query: str, *, page: int = 1, max_results: int = 20):
            _ = query, page, max_results
            return []

    register_live_supplier_client("fashionphile", _LiveFashionphileClient)
    resolution = LiveSupplierResolver().resolve("fashionphile")

    assert resolution.client is not None
    assert resolution.client.search_products("wallet") == []


def test_existing_discovery_pipeline_unchanged_with_fixture_fallback() -> None:
    supplier_client = LiveSupplierResolver().resolve("fashionphile").client
    assert supplier_client is not None

    runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    direct_fixture = FashionphileClient()
    direct_batch = DiscoveryRunner(
        supplier_client=direct_fixture,
        market_connector=SupplierMarketConnector(
            supplier_client=direct_fixture,
            market_client=FakeYahooAuctionClient(),
        ),
    ).evaluate_products(direct_fixture.search_products("Chanel wallet", max_results=1))

    resolved_batch = runner.evaluate_products(supplier_client.search_products("Chanel wallet", max_results=1))

    direct_candidate = next(
        result for result in direct_batch.results if result.status is DiscoveryCandidateStatus.SUCCESS
    )
    resolved_candidate = next(
        result for result in resolved_batch.results if result.status is DiscoveryCandidateStatus.SUCCESS
    )

    assert direct_candidate.profit_result is not None
    assert resolved_candidate.profit_result is not None
    assert resolved_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert resolved_candidate.profit_result.profit_margin == direct_candidate.profit_result.profit_margin
    assert resolved_candidate.profit_result.roi == direct_candidate.profit_result.roi
    assert resolved_candidate.buy_decision is not None
    assert direct_candidate.buy_decision is not None
    assert resolved_candidate.buy_decision.decision == direct_candidate.buy_decision.decision


def test_supplier_http_transport_is_not_implemented() -> None:
    from supplier.live.transport import SupplierHttpTransport

    transport = SupplierHttpTransport()

    with pytest.raises(NotImplementedError):
        transport.get("https://example.invalid/search")
