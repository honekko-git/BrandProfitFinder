"""Tests for discovery CLI human-readable output."""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.cli.discovery_command import DiscoveryCommandOptions, run_discovery_command
from profit_discovery.cli.discovery_output import (
    build_display_summary,
    format_discovery_summary,
    format_export_message,
    format_top_buy_candidates,
    render_discovery_run,
)
from profit_discovery.discovery_runner.models import (
    BatchDiscoveryResult,
    DiscoveryCandidateResult,
    DiscoveryCandidateStatus,
)
from profit_discovery.multi_brand.models import BrandDiscoveryResult, MultiBrandDiscoveryResult
from profit_discovery.models import BuyDecision, BuyDecisionResult
from supplier.models import SupplierProduct, SupplierType


def _candidate(
    *,
    title: str,
    supplier_name: str = "fashionphile",
    decision: BuyDecision = BuyDecision.BUY,
    profit_jpy: int = 25000,
    roi: str = "35.5",
) -> DiscoveryCandidateResult:
    product = SupplierProduct(
        supplier_name=supplier_name,
        external_id="fp-test-001",
        title=title,
        brand="Chanel",
        category="wallets",
        condition=SupplierType.USED.value,
        purchase_price=700.0,
        currency="USD",
        url="https://example.invalid/fashionphile/fp-test-001",
        image_urls=[],
        availability="in_stock",
    )
    profit_result = PriceResult(
        product=Product(name=title, brand="Chanel", price=700.0, currency="USD"),
        profit_jpy=Decimal(str(profit_jpy)),
        roi=Decimal(roi),
        calculation_status="success",
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=profit_result,
        buy_decision=BuyDecisionResult(
            decision=decision,
            max_purchase_price_jpy=Decimal("100000"),
            target_profit_jpy=Decimal("10000"),
            expected_profit_jpy=Decimal(str(profit_jpy)),
            margin_requirement=Decimal("20"),
        ),
    )


def test_format_discovery_summary_includes_brands_and_counts() -> None:
    result = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(
            _candidate(title="Wallet A", decision=BuyDecision.BUY),
            _candidate(title="Wallet B", decision=BuyDecision.HOLD),
            _candidate(title="Wallet C", decision=BuyDecision.PASS),
        ),
        ranked_opportunities=(),
        successful_brands=("CHANEL", "Louis Vuitton", "Hermes"),
        failed_brands=(),
        total_candidates=3,
    )
    summary = build_display_summary(result, brands=["CHANEL", "Louis Vuitton", "Hermes"])
    rendered = format_discovery_summary(summary)

    assert "検索概要" in rendered
    assert "CHANEL" in rendered
    assert "Louis Vuitton" in rendered
    assert "Hermes" in rendered
    assert "商品数:\n3" in rendered
    assert "BUY:\n1" in rendered
    assert "HOLD:\n1" in rendered
    assert "PASS:\n1" in rendered


def test_format_top_buy_candidates_lists_product_supplier_profit_and_roi() -> None:
    rendered = format_top_buy_candidates(
        [
            _candidate(title="Chanel Classic Wallet", profit_jpy=30000, roi="40.0"),
        ],
    )

    assert "BUY候補上位" in rendered
    assert "商品名: Chanel Classic Wallet" in rendered
    assert "仕入先: fashionphile" in rendered
    assert "利益: 30,000 JPY" in rendered
    assert "ROI: 40.0%" in rendered
    assert "判定: BUY" in rendered


def test_render_discovery_run_shows_empty_case_message() -> None:
    result = MultiBrandDiscoveryResult(
        results=(
            BrandDiscoveryResult(
                brand="Hermes",
                batch_result=BatchDiscoveryResult(
                    total_products=0,
                    evaluated_products=0,
                    buy_candidates=0,
                    results=(),
                ),
                metadata={"status": "SUCCESS", "product_count": 0},
            ),
        ),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=("Hermes",),
        failed_brands=(),
        total_candidates=0,
    )

    rendered = render_discovery_run(result, brands=["Hermes"])

    assert "商品数:\n0" in rendered
    assert "BUY候補上位" in rendered
    assert "（なし）" in rendered
    assert "結果なし:" in rendered
    assert "Hermes: 0 products found" in rendered


def test_run_discovery_command_prints_export_message(tmp_path: Path) -> None:
    runner = MagicMock()
    runner.run.return_value = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(_candidate(title="Chanel Classic Wallet"),),
        ranked_opportunities=(),
        successful_brands=("Chanel",),
        failed_brands=(),
        total_candidates=1,
    )
    output = io.StringIO()
    export_path = tmp_path / "discovery_report.xlsx"

    with patch(
        "profit_discovery.cli.discovery_command.export_discovery_report",
        return_value=export_path,
    ):
        run_discovery_command(
            DiscoveryCommandOptions(brands=["Chanel"], export=True),
            runner=runner,
            output=output,
        )

    rendered = output.getvalue()
    assert "Excelをエクスポートしました:" in rendered
    assert "discovery_report.xlsx" in rendered


def test_format_export_message_uses_display_path() -> None:
    message = format_export_message(Path("output/discovery_report.xlsx"))
    assert message == "Excelをエクスポートしました:\n\noutput/discovery_report.xlsx"
