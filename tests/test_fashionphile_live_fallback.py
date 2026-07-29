"""Tests for Fashionphile live fallback and discovery compatibility."""

from __future__ import annotations

from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from supplier.factory import create_supplier_client
from supplier.fashionphile.client import FashionphileClient
from supplier.fashionphile.exceptions import FashionphileLiveUnavailableError
from supplier.fashionphile.resolver import FashionphileResolver, FashionphileSourceMode
from supplier.fashionphile.settings import FashionphileSettings
from supplier.models import SupplierProduct, SupplierType


class _UnavailableLiveClient:
    @property
    def supplier_name(self) -> str:
        return "fashionphile"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.USED

    def search_products(self, query: str, *, page: int = 1, max_results: int = 20) -> list[SupplierProduct]:
        raise FashionphileLiveUnavailableError("live unavailable")


def test_fashionphile_resolver_uses_fixture_when_live_disabled() -> None:
    resolution = FashionphileResolver().resolve(settings=FashionphileSettings.default())

    assert resolution.mode is FashionphileSourceMode.FIXTURE
    assert isinstance(resolution.client, FashionphileClient)


def test_fashionphile_resolver_falls_back_to_fixture_when_live_unavailable() -> None:
    resolution = FashionphileResolver().resolve(
        live_client=_UnavailableLiveClient(),
    )

    products = resolution.client.search_products("Chanel wallet", max_results=1)

    assert resolution.mode is FashionphileSourceMode.LIVE
    assert len(products) == 1
    assert products[0].brand == "Chanel"


def test_fashionphile_live_enabled_resolution_falls_back_on_transport_unavailability() -> None:
    resolution = FashionphileResolver().resolve(
        settings=FashionphileSettings(
            enabled=True,
            use_live=True,
            endpoint="https://example.invalid/fashionphile",
        ),
    )

    products = resolution.client.search_products("Chanel wallet", max_results=1)

    assert resolution.mode is FashionphileSourceMode.LIVE
    assert len(products) == 1
    assert products[0].supplier_name == "fashionphile"


def test_existing_factory_client_remains_fixture_backed() -> None:
    client = create_supplier_client("fashionphile")

    assert client is not None
    assert isinstance(client, FashionphileClient)


def test_existing_discovery_pipeline_unchanged_with_fixture_fallback_client() -> None:
    fixture_client = FashionphileClient()
    resolved_client = FashionphileResolver().resolve(
        live_client=_UnavailableLiveClient(),
    ).client

    direct_batch = DiscoveryRunner(
        supplier_client=fixture_client,
        market_connector=SupplierMarketConnector(
            supplier_client=fixture_client,
            market_client=FakeYahooAuctionClient(),
        ),
    ).evaluate_products(fixture_client.search_products("Chanel wallet", max_results=1))

    resolved_batch = DiscoveryRunner(
        supplier_client=resolved_client,
        market_connector=SupplierMarketConnector(
            supplier_client=resolved_client,
            market_client=FakeYahooAuctionClient(),
        ),
    ).evaluate_products(resolved_client.search_products("Chanel wallet", max_results=1))

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
