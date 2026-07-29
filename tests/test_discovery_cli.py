"""Tests for discovery CLI argument parsing and command wiring."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.cli.discovery_command import (
    DiscoveryCommandOptions,
    build_discovery_parser,
    export_discovery_report,
    parse_brands,
    run_discovery_cli,
    run_discovery_command,
)
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult
from profit_discovery.models import BuyDecision, BuyDecisionResult
from supplier.models import SupplierProduct, SupplierType


def test_parse_brands_splits_comma_separated_values() -> None:
    assert parse_brands("CHANEL,LouisVuitton,Hermes") == [
        "CHANEL",
        "Louis Vuitton",
        "Hermes",
    ]


def test_build_discovery_parser_parses_arguments() -> None:
    parser = build_discovery_parser()
    namespace = parser.parse_args(
        [
            "--brands",
            "Chanel,Gucci",
            "--category",
            "wallet",
            "--keyword",
            "classic",
            "--export",
            "--max-results-per-brand",
            "5",
        ],
    )

    options = DiscoveryCommandOptions.from_namespace(namespace)

    assert options.brands == ["Chanel", "Gucci"]
    assert options.category == "wallet"
    assert options.keyword == "classic"
    assert options.export is True
    assert options.max_results_per_brand == 5


def test_run_discovery_command_invokes_runner_with_request() -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=(),
        failed_brands=(),
        total_candidates=0,
    )
    options = DiscoveryCommandOptions(
        brands=["Chanel", "Louis Vuitton"],
        category="wallet",
        keyword="classic",
        max_results_per_brand=3,
    )

    result = run_discovery_command(options, runner=runner)

    assert result.total_candidates == 0
    runner.run.assert_called_once()
    request = runner.run.call_args.args[0]
    assert request.brands == ["Chanel", "Louis Vuitton"]
    assert request.category == "wallet"
    assert request.keyword == "classic"
    assert request.max_results_per_brand == 3


def test_run_discovery_command_exports_when_flag_set(tmp_path) -> None:
    supplier_product = SupplierProduct(
        supplier_name="fashionphile",
        external_id="fp-chanel-wallet-001",
        title="Chanel Classic Wallet",
        brand="Chanel",
        category="wallets",
        condition=SupplierType.USED.value,
        purchase_price=700.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-chanel-wallet-001",
        image_urls=[],
        availability="in_stock",
    )
    profit_result = PriceResult(
        product=Product(name="Chanel Classic Wallet", brand="Chanel", price=700.0, currency="USD"),
        profit_jpy=Decimal("10000"),
        calculation_status="success",
    )
    candidate = DiscoveryCandidateResult(
        supplier_product=supplier_product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=profit_result,
        buy_decision=BuyDecisionResult(
            decision=BuyDecision.BUY,
            max_purchase_price_jpy=Decimal("100000"),
            target_profit_jpy=Decimal("10000"),
            expected_profit_jpy=Decimal("10000"),
            margin_requirement=Decimal("20"),
        ),
    )
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(candidate,),
        ranked_opportunities=(),
        successful_brands=("Chanel",),
        failed_brands=(),
        total_candidates=1,
    )

    with patch(
        "profit_discovery.cli.discovery_command.export_discovery_report",
        return_value=tmp_path / "discovery_report.xlsx",
    ) as export_mock:
        run_discovery_command(
            DiscoveryCommandOptions(brands=["Chanel"], export=True),
            runner=runner,
        )

    export_mock.assert_called_once()


def test_run_discovery_cli_returns_zero_on_success() -> None:
    with patch(
        "profit_discovery.cli.discovery_command.run_discovery_command",
        return_value=MultiBrandDiscoveryResult(
            results=(),
            ranked_candidates=(),
            ranked_opportunities=(),
            successful_brands=(),
            failed_brands=(),
            total_candidates=0,
        ),
    ):
        assert (
            run_discovery_cli(
                ["--brands", "Chanel"],
            )
            == 0
        )


def test_export_discovery_report_returns_none_without_candidates() -> None:
    result = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=(),
        failed_brands=(),
        total_candidates=0,
    )

    assert export_discovery_report(result) is None
