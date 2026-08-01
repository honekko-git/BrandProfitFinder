"""CLI integration tests for showcase dashboard output."""

from __future__ import annotations

import io

from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_command
from profit_discovery.discovery_runner import DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRunner
from supplier.fashionphile.client import FashionphileClient


def _runner() -> MultiBrandDiscoveryRunner:
    supplier_client = FashionphileClient()
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


def test_showcase_cli_output_includes_dashboard_view() -> None:
    output = io.StringIO()
    run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=_runner(),
        output=output,
    )

    rendered = output.getvalue()
    assert "AI利益発見ショーケース" in rendered
    assert "注目候補" in rendered
    assert "概要:" in rendered
    assert "候補合計:" in rendered
    assert "需要込み候補順位" in rendered
    assert "検索概要" in rendered
