"""Tests for discovery CLI error handling and continuation."""

from __future__ import annotations

import io
from unittest.mock import patch

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_cli, run_discovery_command
from profit_discovery.cli.discovery_output import render_discovery_run
from profit_discovery.discovery_runner import DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryResult, MultiBrandDiscoveryRunner
from supplier.base import SupplierClient
from supplier.fashionphile.client import FashionphileClient
from supplier.models import SupplierProduct, SupplierType


class _BrandAwareFailingSupplierClient:
    def __init__(self, *, inner: SupplierClient, failing_brand: str) -> None:
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


def _runner(*, failing_brand: str | None = None) -> MultiBrandDiscoveryRunner:
    inner = FashionphileClient()
    supplier_client: SupplierClient = inner
    if failing_brand is not None:
        supplier_client = _BrandAwareFailingSupplierClient(inner=inner, failing_brand=failing_brand)
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=inner,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


def test_render_discovery_run_summarizes_supplier_failure() -> None:
    result = _runner(failing_brand="Gucci").run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Gucci"],
            max_results_per_brand=2,
        ),
    )

    rendered = render_discovery_run(result, brands=["Chanel", "Gucci"])

    assert "Issues" in rendered
    assert "Supplier failures:" in rendered
    assert "Gucci: brand search failed" in rendered
    assert "Products:" in rendered


def test_render_discovery_run_summarizes_market_failure() -> None:
    discovery_runner = DiscoveryRunner(
        supplier_client=FashionphileClient(),
        market_connector=SupplierMarketConnector(
            supplier_client=FashionphileClient(),
            market_client=FakeYahooAuctionClient(),
        ),
    )
    unknown_product = SupplierProduct(
        supplier_name="fashionphile",
        external_id="no-market-001",
        title="Unknown Luxury Item",
        brand="UnknownBrand",
        category="misc",
        condition=SupplierType.USED.value,
        purchase_price=100.0,
        currency="USD",
        url="https://example.invalid/unknown",
        image_urls=[],
        availability="in_stock",
    )
    batch = discovery_runner.evaluate_products([unknown_product])
    result = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=batch.results,
        ranked_opportunities=(),
        successful_brands=("UnknownBrand",),
        failed_brands=(),
        total_candidates=1,
    )

    rendered = render_discovery_run(result, brands=["UnknownBrand"])

    assert "Market failures:" in rendered
    assert "UnknownBrand / Unknown Luxury Item" in rendered
    assert "no_domestic_market_price" in rendered


def test_run_discovery_command_continues_after_supplier_failure() -> None:
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(brands=["Chanel", "Gucci"], max_results_per_brand=2),
        runner=_runner(failing_brand="Gucci"),
        output=output,
    )

    assert "Chanel" in result.successful_brands
    assert result.failed_brands == ("Gucci",)
    assert result.total_candidates >= 1
    rendered = output.getvalue()
    assert "Supplier failures:" in rendered
    assert "Discovery Summary" in rendered


def test_run_discovery_cli_returns_zero_when_one_brand_fails() -> None:
    with patch(
        "profit_discovery.cli.discovery_command.run_discovery_command",
        return_value=MultiBrandDiscoveryResult(
            results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=("Chanel",),
            failed_brands=("Gucci",),
            total_candidates=1,
        ),
    ):
        assert run_discovery_cli(["--brands", "Chanel,Gucci"]) == 0
