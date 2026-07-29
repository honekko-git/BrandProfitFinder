"""Tests for multi-brand discovery failure isolation."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from supplier.base import SupplierClient
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType


class _BrandAwareFailingSupplierClient:
    """Fail only when the search query targets the configured failing brand."""

    def __init__(
        self,
        *,
        inner: SupplierClient,
        failing_brand: str,
    ) -> None:
        self._inner = inner
        self._failing_brand = failing_brand.lower()

    @property
    def supplier_name(self) -> str:
        return self._inner.supplier_name

    @property
    def supplier_type(self) -> SupplierType:
        return self._inner.supplier_type

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        if self._failing_brand in query.lower():
            raise RuntimeError("brand search failed")
        return self._inner.search_products(query, page=page, max_results=max_results)


def _runner(*, failing_brand: str) -> MultiBrandDiscoveryRunner:
    inner = FashionphileClient()
    supplier_client = _BrandAwareFailingSupplierClient(
        inner=inner,
        failing_brand=failing_brand,
    )
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=inner,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


def test_multi_brand_runner_continues_when_one_brand_fails() -> None:
    result = _runner(failing_brand="Gucci").run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Gucci", "Louis Vuitton"],
            max_results_per_brand=3,
        ),
    )

    assert "Chanel" in result.successful_brands
    assert "Louis Vuitton" in result.successful_brands
    assert result.failed_brands == ("Gucci",)
    assert result.total_candidates >= 2

    statuses = {item.brand: item.metadata.get("status") for item in result.results}
    assert statuses["Chanel"] == "SUCCESS"
    assert statuses["Gucci"] == "ERROR"
    assert statuses["Louis Vuitton"] == "SUCCESS"
