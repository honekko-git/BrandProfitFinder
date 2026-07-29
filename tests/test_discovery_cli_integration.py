"""Integration tests for discovery CLI through the existing discovery pipeline."""

from __future__ import annotations

from pathlib import Path

import openpyxl
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    export_discovery_report,
    run_discovery_command,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from supplier.fashionphile.client import FashionphileClient


def _discovery_runner() -> DiscoveryRunner:
    supplier_client = FashionphileClient()
    return DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )


def test_discovery_cli_runs_multi_brand_runner_pipeline() -> None:
    discovery_runner = _discovery_runner()
    options = DiscoveryCommandOptions(
        brands=["Chanel"],
        keyword="wallet",
        max_results_per_brand=1,
    )

    direct_result = MultiBrandDiscoveryRunner(discovery_runner=discovery_runner).run(
        MultiBrandDiscoveryRequest(
            brands=options.brands,
            keyword=options.keyword,
            max_results_per_brand=options.max_results_per_brand,
        ),
    )
    cli_result = run_discovery_command(
        options,
        runner=MultiBrandDiscoveryRunner(discovery_runner=discovery_runner),
    )

    direct_candidate = next(
        candidate
        for candidate in direct_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    )
    cli_candidate = next(
        candidate
        for candidate in cli_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    )

    assert direct_candidate.profit_result is not None
    assert cli_candidate.profit_result is not None
    assert cli_candidate.profit_result.profit_jpy == direct_candidate.profit_result.profit_jpy
    assert cli_candidate.profit_result.profit_margin == direct_candidate.profit_result.profit_margin
    assert cli_candidate.profit_result.roi == direct_candidate.profit_result.roi
    assert cli_candidate.buy_decision is not None
    assert direct_candidate.buy_decision is not None
    assert cli_candidate.buy_decision.decision == direct_candidate.buy_decision.decision


def test_discovery_cli_export_writes_excel_report(tmp_path: Path) -> None:
    discovery_runner = _discovery_runner()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
        runner=MultiBrandDiscoveryRunner(discovery_runner=discovery_runner),
    )

    export_path = export_discovery_report(result, output_dir=tmp_path)
    assert export_path is not None
    assert export_path.exists()

    workbook = openpyxl.load_workbook(export_path)
    assert "Profit Analysis" in workbook.sheetnames

    successful = [
        candidate
        for candidate in result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS and candidate.profit_result is not None
    ]
    assert successful
    assert all(candidate.profit_result.profit_jpy > 0 for candidate in successful)
