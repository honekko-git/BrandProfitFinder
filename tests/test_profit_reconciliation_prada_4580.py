"""Regression: Fashionphile Prada ¥111,200 / ¥159,736 / ¥4,580 reconciliation."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from marketplace.acquisition_workspace.detail_display import build_sourcing_detail
from marketplace.acquisition_workspace.ranking import resolve_net_profit
from models.product import Product
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from profit_policy.money import round_jpy
from profit_policy.tax_policy import TaxPolicy
from tests.acquisition_test_helpers import make_candidate


PURCHASE_USD = Decimal("695")
EXCHANGE = Decimal("160")
PURCHASE_JPY = Decimal("111200")
SALE_JPY = Decimal("159736")
EXPECTED_PROFIT = Decimal("4580")


def _expected_components() -> dict[str, Decimal]:
    """Exact ImportCostEngine + marketplace fee stack for the live ranking row."""
    intl = ProfitConfig().international_shipping_jpy  # 3000
    customs_base = PURCHASE_JPY + intl
    duty, import_tax = TaxPolicy().compute_import_charges(customs_base)
    domestic_ship = ProfitConfig().domestic_shipping_jpy  # 1000
    fee = round_jpy(SALE_JPY * ProfitConfig().marketplace_fee_rate)
    total_cost = PURCHASE_JPY + intl + duty + import_tax + domestic_ship
    profit = SALE_JPY - total_cost - fee
    return {
        "international_shipping_jpy": intl,
        "customs_duty_jpy": duty,
        "import_tax_jpy": import_tax,
        "domestic_shipping_jpy": domestic_ship,
        "marketplace_fee_jpy": fee,
        "total_cost_jpy": total_cost,
        "profit_jpy": profit,
    }


def test_profit_calculator_reconciles_prada_4580_case() -> None:
    expected = _expected_components()
    assert expected["profit_jpy"] == EXPECTED_PROFIT
    assert expected["customs_duty_jpy"] == Decimal("11420")
    assert expected["import_tax_jpy"] == Decimal("12562")
    assert expected["marketplace_fee_jpy"] == Decimal("15974")
    assert expected["total_cost_jpy"] == Decimal("139182")

    product = Product(
        name="Prada Tessuto Nylon Saffiano Re-Edition 2006 Shoulder Bag Black",
        brand="Prada",
        price=float(PURCHASE_USD),
        currency="USD",
        store_name="Fashionphile",
        exchange_rate=float(EXCHANGE),
    )
    result = ProfitCalculator().calculate(product, SALE_JPY, domestic_market="yahoo_auction")

    assert result.purchase_price_jpy == PURCHASE_JPY
    assert result.domestic_sale_price_jpy == SALE_JPY
    assert result.international_shipping_jpy == expected["international_shipping_jpy"]
    assert result.customs_duty_jpy == expected["customs_duty_jpy"]
    assert result.import_tax_jpy == expected["import_tax_jpy"]
    assert result.domestic_shipping_jpy == expected["domestic_shipping_jpy"]
    assert result.marketplace_fee_jpy == expected["marketplace_fee_jpy"]
    assert result.other_costs_jpy == Decimal("0")
    assert result.total_cost_jpy == expected["total_cost_jpy"]
    assert result.profit_jpy == EXPECTED_PROFIT

    # No double-count: sale - purchase - (non-purchase costs) - fee == profit
    non_purchase = (
        result.international_shipping_jpy
        + result.customs_duty_jpy
        + result.import_tax_jpy
        + result.domestic_shipping_jpy
        + result.other_costs_jpy
    )
    assert SALE_JPY - PURCHASE_JPY - non_purchase - result.marketplace_fee_jpy == EXPECTED_PROFIT
    spread = SALE_JPY - PURCHASE_JPY
    assert spread - EXPECTED_PROFIT == Decimal("43956")


def test_ranking_workspace_detail_agree_on_4580() -> None:
    candidate = replace(
        make_candidate(
            title="Prada Tessuto Nylon Saffiano Re-Edition 2006 Shoulder Bag Black",
            brand="Prada",
            selected=True,
            purchase_price=PURCHASE_USD,
        ),
        purchase_price_jpy=PURCHASE_JPY,
        last_gross_profit=EXPECTED_PROFIT,
        last_net_profit=None,
        last_profit_batch_id="batch-prada-audit",
        last_profit_checked_at="2026-07-31T18:53:20+00:00",
        last_warning="NET_COST_INCOMPLETE",
    )
    assert resolve_net_profit(candidate) == EXPECTED_PROFIT

    expected = _expected_components()
    batch_result = SimpleNamespace(
        candidate=SimpleNamespace(
            candidate_id=candidate.candidate_id,
            purchase_price_jpy=PURCHASE_JPY,
            purchase_price=PURCHASE_USD,
            currency="USD",
        ),
        domestic=SimpleNamespace(
            recommended_selling_estimate_jpy=SALE_JPY,
            median_jpy=SALE_JPY,
            accepted_count=3,
            minimum_jpy=SALE_JPY,
            maximum_jpy=SALE_JPY,
            reliability="MEDIUM",
        ),
        estimated_costs=SimpleNamespace(
            exchange_rate="160 JPY/USD",
            domestic_platform_fee_jpy=Decimal("0"),
            payment_fee_jpy=Decimal("0"),
            domestic_shipping_jpy=Decimal("0"),
            international_shipping_jpy=Decimal("0"),
            import_duty_jpy=Decimal("0"),
            import_tax_jpy=Decimal("0"),
            forwarding_fee_jpy=Decimal("0"),
            inspection_or_repair_reserve_jpy=Decimal("0"),
            miscellaneous_cost_jpy=Decimal("0"),
            net_profit_complete=False,
        ),
        gross_estimated_profit=EXPECTED_PROFIT,
        net_estimated_profit=None,
        accepted_comparable_count=3,
        operational_trace={
            "profit": {
                "domestic_predicted_sale_price_jpy": str(SALE_JPY),
                "gross_estimated_profit_jpy": str(EXPECTED_PROFIT),
                "cost_breakdown": {
                    "source": "ProfitCalculator/ImportCostEngine",
                    "purchase_price_jpy": str(PURCHASE_JPY),
                    "international_shipping_jpy": str(expected["international_shipping_jpy"]),
                    "customs_duty_jpy": str(expected["customs_duty_jpy"]),
                    "import_tax_jpy": str(expected["import_tax_jpy"]),
                    "domestic_shipping_jpy": str(expected["domestic_shipping_jpy"]),
                    "marketplace_fee_jpy": str(expected["marketplace_fee_jpy"]),
                    "other_costs_jpy": "0",
                    "payment_fee_jpy": "0",
                    "insurance_jpy": "0",
                    "packaging_jpy": "0",
                    "domestic_market": "yahoo_auction",
                    "total_cost_jpy": str(expected["total_cost_jpy"]),
                    "profit_jpy": str(EXPECTED_PROFIT),
                },
                "cost_profile_breakdown": {"net_profit_complete": False},
            }
        },
    )

    rank = SimpleNamespace(
        net_profit=EXPECTED_PROFIT,
        roi=Decimal("4.1"),
        overall_score=Decimal("80"),
        confidence_level="MEDIUM",
        analysis_summary="audit",
        ranking_warnings=(),
        sales_count=3,
        source_listing_url=candidate.purchase_url,
    )
    detail = build_sourcing_detail(
        candidate=candidate,
        rank=rank,
        batch_result=batch_result,
        batch_id="ws-audit",
        selling_estimate=SALE_JPY,
    )
    assert detail.profit == "¥4,580"
    assert detail.net_profit == "¥4,580"
    labels = dict(detail.breakdown)
    assert labels["予測販売価格"] == "¥159,736"
    assert labels["仕入価格"] == "¥111,200"
    assert labels["国際送料"] == "¥3,000"
    assert labels["関税"] == "¥11,420"
    assert labels["輸入消費税"] == "¥12,562"
    assert labels["国内送料"] == "¥1,000"
    assert labels["Yahooオークション販売手数料"] == "¥15,974"
    assert labels["決済手数料"] == "¥0"
    assert labels["保険"] == "¥0"
    assert labels["梱包費"] == "¥0"
    assert labels["その他固定費"] == "¥0"
    assert "eBay" not in "".join(labels.keys())
    final_keys = [k for k in labels if k.startswith("最終利益")]
    assert final_keys
    assert labels[final_keys[0]] == "¥4,580"

    from marketplace.acquisition_workspace.detail_display import reconcile_breakdown_rows

    check = reconcile_breakdown_rows(detail.breakdown)
    assert check["reconciles"] is True
    assert check["expected_profit"] == EXPECTED_PROFIT
    assert check["cost_total"] == Decimal("43956")


def test_detail_breakdown_never_shows_ebay_for_yahoo_fee_schedule() -> None:
    from marketplace.acquisition_workspace.detail_display import _marketplace_fee_label

    label = _marketplace_fee_label(batch_result=SimpleNamespace(yahoo_marketplace="Yahoo Auctions"), domestic_market="yahoo_auction")
    assert "Yahoo" in label
    assert "eBay" not in label
    mercari = _marketplace_fee_label(batch_result=SimpleNamespace(yahoo_marketplace="Mercari"), domestic_market="mercari")
    assert "メルカリ" in mercari
    ebay = _marketplace_fee_label(batch_result=SimpleNamespace(yahoo_marketplace=""), domestic_market="ebay")
    assert "eBay" in ebay
