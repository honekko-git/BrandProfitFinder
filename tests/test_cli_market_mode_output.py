"""Tests for discovery CLI market mode output."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from marketplace.domestic_market import FakeYahooAuctionTransport
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    build_domestic_market_runtime_config,
    run_discovery_command,
)
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult


def test_cli_output_shows_fixture_market_mode() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        ranked_demand_opportunities=(),
        successful_brands=("CHANEL",),
        failed_brands=(),
        total_candidates=0,
    )
    output = io.StringIO()

    run_discovery_command(
        DiscoveryCommandOptions(brands=["CHANEL"]),
        runner=runner,
        output=output,
    )

    rendered = output.getvalue()
    assert "要求市場モード:" in rendered
    assert "FIXTURE" in rendered
    assert "実際の市場ソース:" in rendered
    assert "Fixture" in rendered
    assert "フォールバック:\nいいえ" in rendered


def test_cli_output_shows_live_market_mode() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        ranked_demand_opportunities=(),
        successful_brands=("CHANEL",),
        failed_brands=(),
        total_candidates=0,
    )
    output = io.StringIO()

    run_discovery_command(
        DiscoveryCommandOptions(brands=["CHANEL"], live_market=True),
        runner=runner,
        output=output,
    )

    rendered = output.getvalue()
    assert "要求市場モード:" in rendered
    assert "要求市場モード:\nLIVE" in rendered
    assert "実際の市場ソース:" in rendered
    assert "フォールバック:" in rendered


def test_cli_showcase_output_keeps_existing_fields() -> None:
    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet Black Caviar", "sold_price": 155000},
            {"title": "Chanel CC Wallet Medium", "sold_price": 160000},
        ]
    )
    runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )
    output = io.StringIO()

    run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=runner,
        injected_transport=transport,
        output=output,
    )

    rendered = output.getvalue()
    assert "検索概要" in rendered
    assert "需要込み候補順位" in rendered
    assert "AI利益発見ショーケース" in rendered
    assert "注目候補" in rendered
    assert "概要:" in rendered
    assert "候補合計:" in rendered
    assert "利益:" in rendered
    assert "ROI:" in rendered
    assert "判定:" in rendered
