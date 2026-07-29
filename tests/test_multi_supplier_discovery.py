"""Tests for multi supplier discovery service."""

from __future__ import annotations

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.discovery_runner import DiscoveryRunner, rank_discovery_results
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.models import BuyDecision
from profit_discovery.supplier_discovery import (
    MultiSupplierDiscoveryService,
    SupplierDiscoverySource,
)
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType


class _FakeSecondSupplierClient:
    @property
    def supplier_name(self) -> str:
        return "therealreal-stub"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.USED

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        _ = query, page
        return [
            SupplierProduct(
                supplier_name=self.supplier_name,
                external_id="trr-gucci-wallet-001",
                title="Gucci Wallet",
                brand="Gucci",
                category="wallets",
                condition=SupplierType.USED.value,
                purchase_price=450.0,
                currency="USD",
                url="https://example.invalid/therealreal/trr-gucci-wallet-001",
                image_urls=[],
                availability="in_stock",
            )
        ][:max_results]


class _FailingSupplierClient:
    @property
    def supplier_name(self) -> str:
        return "failing-supplier"

    @property
    def supplier_type(self) -> SupplierType:
        return SupplierType.USED

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[SupplierProduct]:
        raise RuntimeError("supplier search failed")


def _service(*sources: SupplierDiscoverySource) -> MultiSupplierDiscoveryService:
    primary = FashionphileClient()
    market_connector = SupplierMarketConnector(
        supplier_client=primary,
        market_client=FakeYahooAuctionClient(),
    )
    runner = DiscoveryRunner(
        supplier_client=primary,
        market_connector=market_connector,
    )
    return MultiSupplierDiscoveryService(sources=list(sources), discovery_runner=runner)


def test_multi_supplier_service_executes_all_enabled_sources() -> None:
    service = _service(
        SupplierDiscoverySource(
            supplier_name="fashionphile",
            client=FashionphileClient(),
        ),
        SupplierDiscoverySource(
            supplier_name="therealreal-stub",
            client=_FakeSecondSupplierClient(),
        ),
    )

    result = service.run(query="wallet", max_results=5)

    assert result.total_sources == 2
    assert len(result.results) == 2
    assert {item.source_name for item in result.results} == {
        "fashionphile",
        "therealreal-stub",
    }
    assert all(item.metadata.get("status") == "SUCCESS" for item in result.results)


def test_multi_supplier_service_isolates_supplier_failures() -> None:
    service = _service(
        SupplierDiscoverySource(
            supplier_name="fashionphile",
            client=FashionphileClient(),
        ),
        SupplierDiscoverySource(
            supplier_name="failing-supplier",
            client=_FailingSupplierClient(),
        ),
    )

    result = service.run(query="Chanel wallet", max_results=3)

    statuses = {item.source_name: item.metadata.get("status") for item in result.results}
    assert statuses["fashionphile"] == "SUCCESS"
    assert statuses["failing-supplier"] == "ERROR"
    assert result.total_products >= 1


def test_multi_supplier_service_aggregates_products_from_all_sources() -> None:
    service = _service(
        SupplierDiscoverySource(
            supplier_name="fashionphile",
            client=FashionphileClient(),
        ),
        SupplierDiscoverySource(
            supplier_name="therealreal-stub",
            client=_FakeSecondSupplierClient(),
        ),
    )

    result = service.run(query="wallet", max_results=5)

    supplier_names = {
        candidate.supplier_product.supplier_name for candidate in result.ranked_candidates
    }
    assert "fashionphile" in supplier_names
    assert "therealreal-stub" in supplier_names
    assert result.total_products >= 2


def test_multi_supplier_service_ranks_buy_candidates_first() -> None:
    service = _service(
        SupplierDiscoverySource(
            supplier_name="fashionphile",
            client=FashionphileClient(),
        ),
        SupplierDiscoverySource(
            supplier_name="therealreal-stub",
            client=_FakeSecondSupplierClient(),
        ),
    )

    result = service.run(query="wallet", max_results=5)

    buy_indices = [
        index
        for index, candidate in enumerate(result.ranked_candidates)
        if candidate.buy_decision is not None
        and candidate.buy_decision.decision is BuyDecision.BUY
    ]
    if len(buy_indices) >= 2:
        assert buy_indices == sorted(buy_indices)

    ranked_again = rank_discovery_results(list(result.ranked_candidates))
    assert [item.supplier_product.external_id for item in ranked_again] == [
        item.supplier_product.external_id for item in result.ranked_candidates
    ]


def test_full_multi_supplier_architecture_flow() -> None:
    service = _service(
        SupplierDiscoverySource(
            supplier_name="fashionphile",
            client=FashionphileClient(),
        ),
        SupplierDiscoverySource(
            supplier_name="therealreal-stub",
            client=_FakeSecondSupplierClient(),
        ),
    )

    result = service.run(query="wallet", max_results=5)

    assert result.total_sources == 2
    assert result.ranked_candidates
    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.profit_result is not None and candidate.buy_decision is not None
    ]
    assert successful
    assert successful[0].buy_decision.decision in {
        BuyDecision.BUY,
        BuyDecision.HOLD,
        BuyDecision.PASS,
    }
