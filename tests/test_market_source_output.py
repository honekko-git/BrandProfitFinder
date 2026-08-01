"""Tests for market source truth in CLI and showcase output."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from marketplace.domestic_market import FakeYahooAuctionTransport
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    build_domestic_market_runtime_config,
    read_runtime_market_execution,
    run_discovery_command,
)
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult
from profit_discovery.showcase.formatter import ShowcaseFormatter


def test_cli_output_shows_requested_and_actual_market_source() -> None:
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
    assert "実際の市場ソース:" in rendered
    assert "フォールバック:" in rendered
    assert "FIXTURE" in rendered
    assert "Fixture" in rendered
    assert "フォールバック:\nいいえ" in rendered


def test_cli_output_shows_live_execution_truth() -> None:
    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet", "sold_price": 155000},
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
    assert "要求市場モード:\nLIVE" in rendered
    assert "実際の市場ソース:\nYahoo Auction LIVE" in rendered
    assert "フォールバック:\nいいえ" in rendered
    assert "要求モード:\nLIVE" in rendered
    assert "実際の取得元:\nYahoo Auction LIVE" in rendered


def test_showcase_opportunity_includes_market_truth_fields() -> None:
    transport = FakeYahooAuctionTransport(
        default_items=[
            {"title": "Chanel Classic Wallet", "sold_price": 155000},
        ]
    )
    runner = build_default_discovery_runner(
        market_config=build_domestic_market_runtime_config(live_market=True),
        injected_transport=transport,
    )
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["CHANEL"],
            keyword="wallet",
            max_results_per_brand=1,
            live_market=True,
        ),
        runner=runner,
        injected_transport=transport,
        output=io.StringIO(),
    )

    showcase_items = ShowcaseFormatter().to_showcase_opportunities(
        result.ranked_demand_opportunities,
        market_execution=read_runtime_market_execution(runner),
    )
    assert showcase_items
    item = showcase_items[0]
    assert item.requested_market_mode == "LIVE"
    assert item.actual_market_source == "Yahoo Auction LIVE"
    assert item.fallback_used is False
    assert item.market_source == "Yahoo Auction LIVE"
    assert item.profit_jpy is not None
    assert item.decision in {"BUY", "HOLD", "PASS"}
