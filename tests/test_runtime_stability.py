"""Runtime stability checks for V2 discovery pipeline preparation."""

from __future__ import annotations

import importlib
import io
import subprocess
import sys
from pathlib import Path

import pytest
from marketplace.yahoo_auction.client import FakeYahooAuctionClient
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_production_discovery_pipeline,
    run_discovery_command,
)
from profit_discovery.discovery_runner import DiscoveryCandidateStatus, DiscoveryRunner
from profit_discovery.market_connector import SupplierMarketConnector
from profit_discovery.multi_brand import MultiBrandDiscoveryRequest, MultiBrandDiscoveryRunner
from profit_discovery.showcase import ShowcaseFormatter
from supplier.config import SupplierRuntimeConfig
from supplier.fashionphile.client import FashionphileClient
from supplier.factory import resolve_supplier_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent

IMPORT_TARGETS: tuple[tuple[str, str], ...] = (
    ("profit_discovery", "profit_discovery"),
    ("profit_discovery.cli", "profit_discovery.cli"),
    ("profit_discovery.showcase", "profit_discovery.showcase"),
    ("profit_discovery.multi_brand", "profit_discovery.multi_brand"),
    ("profit_discovery.opportunity", "profit_discovery.opportunity"),
    ("profit_intelligence", "profit_intelligence"),
    ("profit_intelligence.demand", "profit_intelligence.demand"),
    ("product_identity", "product_identity"),
    ("product_identity.identity_resolver", "product_identity.identity_resolver"),
    ("product_identity.duplicate_resolver", "product_identity.duplicate_resolver"),
    ("supplier", "supplier"),
    ("supplier.config", "supplier.config"),
    ("supplier.factory", "supplier.factory"),
)


def _discovery_runner() -> MultiBrandDiscoveryRunner:
    supplier_client = FashionphileClient()
    discovery_runner = DiscoveryRunner(
        supplier_client=supplier_client,
        market_connector=SupplierMarketConnector(
            supplier_client=supplier_client,
            market_client=FakeYahooAuctionClient(),
        ),
    )
    return MultiBrandDiscoveryRunner(discovery_runner=discovery_runner)


@pytest.mark.parametrize(("module_name", "label"), IMPORT_TARGETS)
def test_runtime_import_validation(module_name: str, label: str) -> None:
    module = importlib.import_module(module_name)
    assert module.__name__ == label


def test_runtime_default_supplier_config_uses_fixture_mode() -> None:
    config = SupplierRuntimeConfig.default()

    assert config.use_fixture is True
    assert config.enable_live is False

    client = resolve_supplier_client("fashionphile", config=config)
    assert client is not None
    assert client.supplier_name == "fashionphile"


def test_runtime_live_mode_configuration_is_available() -> None:
    config = SupplierRuntimeConfig.live_only()

    assert config.use_fixture is False
    assert config.enable_live is True


def test_runtime_discovery_pipeline_execution_preserves_profit_integrity() -> None:
    runner = _discovery_runner()
    discovery_result = runner.run(
        MultiBrandDiscoveryRequest(
            brands=["Chanel", "Louis Vuitton"],
            keyword="wallet",
            max_results_per_brand=2,
        ),
    )
    ranked = build_production_discovery_pipeline(discovery_result)
    showcase_items = ShowcaseFormatter().to_showcase_opportunities(ranked)

    successful_by_id = {
        candidate.supplier_product.external_id: candidate
        for candidate in discovery_result.ranked_candidates
        if candidate.status is DiscoveryCandidateStatus.SUCCESS
    }
    assert successful_by_id
    assert ranked
    assert showcase_items

    for item, ranked_item in zip(showcase_items, ranked, strict=True):
        external_id = ranked_item.candidate.supplier_product.external_id
        original = successful_by_id[external_id]

        assert original.profit_result is not None
        assert item.profit_jpy == original.profit_result.profit_jpy
        assert item.roi == original.profit_result.roi
        assert original.buy_decision is not None
        assert item.decision == original.buy_decision.decision.value
        assert ranked_item.candidate.profit_result.profit_margin == original.profit_result.profit_margin


def test_runtime_cli_smoke_test_executes_discovery_command() -> None:
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            keyword="wallet",
            max_results_per_brand=1,
        ),
        runner=_discovery_runner(),
        output=output,
    )

    rendered = output.getvalue()
    assert result.total_candidates >= 0
    assert "Discovery Summary" in rendered
    assert "Demand Opportunity Ranking" in rendered
    assert "AI PROFIT DISCOVERY SHOWCASE" in rendered
    assert result.ranked_demand_opportunities is not None


def test_runtime_cli_smoke_test_supports_category_priority_path() -> None:
    output = io.StringIO()
    result = run_discovery_command(
        DiscoveryCommandOptions(
            brands=["Chanel"],
            category_priority="HIGH",
            max_results_per_brand=1,
        ),
        runner=_discovery_runner(),
        output=output,
    )

    rendered = output.getvalue()
    assert result.total_candidates >= 0
    assert "Discovery Summary" in rendered
    assert "Chanel" in rendered
    assert "AI PROFIT DISCOVERY SHOWCASE" in rendered
    assert result.ranked_demand_opportunities is not None


def test_runtime_main_discovery_entrypoint_smoke() -> None:
    completed = subprocess.run(
        [sys.executable, "main.py", "discovery", "--brands", "Chanel", "--keyword", "wallet", "--max-results-per-brand", "1"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Discovery Summary" in completed.stdout
    assert "Demand Opportunity Ranking" in completed.stdout
    assert "AI PROFIT DISCOVERY SHOWCASE" in completed.stdout
