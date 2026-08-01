"""Tests for used luxury discovery CLI behavior."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from profit_discovery.config.used_luxury import UsedLuxuryModeConfig
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_default_discovery_runner,
    build_discovery_parser,
    resolve_discovery_brands,
    run_discovery_command,
)
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult


def test_discovery_parser_accepts_used_luxury_flag() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(["--used-luxury"])

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.used_luxury is True
    assert options.brands == [
        "Chanel",
        "Louis Vuitton",
        "Hermes",
        "Miu Miu",
    ]


def test_used_luxury_defaults_to_s_tier_brands() -> None:
    brands = resolve_discovery_brands(
        tier="S",
        used_luxury_config=UsedLuxuryModeConfig.default(),
    )

    assert brands == ["Chanel", "Louis Vuitton", "Hermes", "Miu Miu"]


def test_used_luxury_cli_output_shows_mode_and_markets() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        ranked_demand_opportunities=(),
        successful_brands=("Chanel",),
        failed_brands=(),
        total_candidates=0,
    )
    output = io.StringIO()

    run_discovery_command(
        DiscoveryCommandOptions(brands=["Chanel"], used_luxury=True),
        runner=runner,
        output=output,
    )

    rendered = output.getvalue()
    assert "モード:\nUSED LUXURY" in rendered
    assert "市場:\nYahoo Auction\nMercari" in rendered


def test_used_luxury_runner_includes_mercari_market() -> None:
    runner = build_default_discovery_runner(used_luxury=True)
    aggregator = runner.discovery_runner.market_connector.market_aggregator

    assert aggregator is not None
    assert len(aggregator.clients) == 2
    assert aggregator.clients[0][0].name == "yahoo_auction"
    assert aggregator.clients[1][0].name == "mercari"
