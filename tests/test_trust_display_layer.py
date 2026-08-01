"""Trust and transparency display layer (presentation only)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from marketplace.acquisition_workspace.detail_display import (
    _cost_settings_rows,
    _trust_summary_rows,
    build_sourcing_detail,
)
from marketplace.acquisition_workspace.price_display import build_price_cells
from marketplace.acquisition_workspace.trust_display import (
    TrustRisk,
    build_trust_summary,
    format_latest_sold_display,
    trust_summary_from_profit_trace,
)


def test_selling_evidence_and_freshness_in_trust_summary() -> None:
    summary = build_trust_summary(
        comparable_quality={
            "quality": "HIGH",
            "publish_price": True,
            "sold_confirmed_count": 8,
            "same_model_matches": 5,
            "marketplaces": "Yahoo Auctions",
            "freshness_label": "2026年7月〜8月",
            "latest_sold_date": "2026-08-01",
            "oldest_sold_date": "2026-07-15",
        }
    )
    assert summary.selling_confidence == "HIGH"
    assert "比較件数: 8件" in summary.selling_note
    assert "データ期間: 2026年7月〜8月" in summary.selling_note
    assert summary.freshness_label == "2026年7月〜8月"
    assert format_latest_sold_display("2026-08-01") == "2026年8月1日"


def test_risk_summary_combines_warnings() -> None:
    danger = build_trust_summary(
        comparable_quality={"quality": "HIGH", "publish_price": True, "sold_confirmed_count": 5},
        new_market_validation={"risk": "CRITICAL", "reason": "新品価格が中古予想を下回る"},
    )
    assert danger.overall_risk == TrustRisk.DANGER
    assert "新品価格" in danger.risk_reason

    warn = build_trust_summary(
        comparable_quality={"quality": "LOW", "publish_price": True, "sold_confirmed_count": 2},
        new_market_validation={"risk": "NONE"},
    )
    assert warn.overall_risk == TrustRisk.WARNING

    safe = build_trust_summary(
        comparable_quality={
            "quality": "HIGH",
            "publish_price": True,
            "sold_confirmed_count": 5,
            "freshness_label": "2026年8月",
        },
        new_market_validation={"risk": "NORMAL"},
    )
    assert safe.overall_risk == TrustRisk.SAFE


def test_critical_new_price_remains_visible_in_price_cells() -> None:
    rows = [SimpleNamespace(candidate_id="c1", purchase_price_jpy=Decimal("104000"), purchase_price=650, currency="USD")]
    cells = build_price_cells(
        rows,
        selling_estimate_by_id={"c1": Decimal("120000")},
        selling_meta_by_id={
            "c1": {
                "quality": "MEDIUM",
                "summary": "比較件数: 3件",
                "selling_confidence": "MEDIUM",
                "freshness_label": "2026年8月",
                "new_market_risk": "CRITICAL",
                "overall_risk": "DANGER",
                "risk_reason": "新品価格が中古予想を下回る",
                "latest_sold_date": "2026年8月1日",
            }
        },
    )
    assert cells["c1"]["selling"] == "¥120,000"
    assert cells["c1"]["new_market_risk"] == "CRITICAL"
    assert cells["c1"]["overall_risk"] == "DANGER"
    assert cells["c1"]["freshness_label"] == "2026年8月"


def test_cost_breakdown_and_trust_rows_from_trace() -> None:
    batch_result = SimpleNamespace(
        candidate=SimpleNamespace(purchase_price_jpy=Decimal("104000")),
        operational_trace={
            "profit": {
                "overseas_price_jpy": "104000",
                "comparable_quality": {
                    "quality": "HIGH",
                    "publish_price": True,
                    "sold_confirmed_count": 5,
                    "same_model_matches": 5,
                    "freshness_label": "2026年7月〜8月",
                    "latest_sold_date": "2026-08-01",
                    "marketplaces": "Yahoo Auctions",
                },
                "new_market_validation": {"risk": "NORMAL"},
                "cost_profile_breakdown": {
                    "calculation_source": "標準CostProfile",
                    "international_shipping_jpy": "3000",
                    "import_duty_rate": "0.10",
                    "import_tax_rate": "0.10",
                    "domestic_shipping_jpy": "1000",
                    "domestic_platform_fee_rate": "0.10",
                    "payment_fee_rate": "0.0",
                    "payment_fee_jpy": "0",
                },
            }
        },
    )
    trust_rows = _trust_summary_rows(batch_result)
    labels = [label for label, _ in trust_rows]
    assert "総合リスク" in labels
    assert "新品価格" in labels

    cost_rows = _cost_settings_rows(batch_result, candidate=batch_result.candidate)
    cost_labels = [label for label, _ in cost_rows]
    assert "輸入コスト詳細" in cost_labels
    assert "関税" in cost_labels
    assert "販売手数料" in cost_labels
    values = dict(cost_rows)
    assert values["関税"] == "10%"
    assert "3,000" in values["送料"] or values["送料"].endswith("3000") or "¥3,000" in values["送料"]


def test_detail_includes_evidence_cost_and_risk() -> None:
    candidate = SimpleNamespace(
        candidate_id="c1",
        brand="Prada",
        title="Prada Saffiano Lux Medium Tote",
        category="Bag",
        source_name="Fashionphile",
        source_type="fashionphile",
        purchase_url="https://example.com",
        purchase_price_jpy=Decimal("152000"),
        purchase_price=Decimal("950"),
        currency="USD",
        last_net_profit=None,
        last_gross_profit=None,
        last_warning="",
        validation_warnings=(),
        data_truth_summary=SimpleNamespace(confidence_level="HIGH", used_estimated_price=False, used_estimated_shipping=False),
        discovery_metadata=SimpleNamespace(comparable_count=5),
    )
    batch_result = SimpleNamespace(
        candidate=candidate,
        domestic=SimpleNamespace(
            accepted_count=5,
            median_jpy=Decimal("155000"),
            minimum_jpy=148000,
            maximum_jpy=160000,
            reliability="HIGH",
            recommended_selling_estimate_jpy=Decimal("155000"),
            comparable_warning="",
        ),
        accepted_comparable_count=5,
        yahoo_best_title="",
        yahoo_best_price_jpy=0,
        yahoo_best_url="",
        yahoo_best_score=0,
        yahoo_best_attributes="",
        yahoo_best_condition="",
        yahoo_marketplace="",
        net_estimated_profit=Decimal("10000"),
        gross_estimated_profit=Decimal("10000"),
        estimated_costs=SimpleNamespace(
            international_shipping_jpy=Decimal("3000"),
            import_duty_jpy=Decimal("10000"),
            import_tax_jpy=Decimal("10000"),
            domestic_shipping_jpy=Decimal("1000"),
            domestic_platform_fee_jpy=Decimal("15500"),
            payment_fee_jpy=Decimal("0"),
            forwarding_fee_jpy=Decimal("0"),
            inspection_or_repair_reserve_jpy=Decimal("0"),
            miscellaneous_cost_jpy=Decimal("0"),
        ),
        operational_trace={
            "profit": {
                "comparable_quality": {
                    "quality": "HIGH",
                    "publish_price": True,
                    "sold_confirmed_count": 5,
                    "same_model_matches": 5,
                    "freshness_label": "2026年7月〜8月",
                    "latest_sold_date": "2026-08-01",
                    "marketplaces": "Yahoo Auctions",
                },
                "new_market_validation": {"risk": "NORMAL", "display_label": "販売価格チェック"},
                "cost_profile_breakdown": {
                    "calculation_source": "標準CostProfile",
                    "international_shipping_jpy": "3000",
                    "import_duty_rate": "0.10",
                    "import_tax_rate": "0.10",
                    "domestic_platform_fee_rate": "0.10",
                    "domestic_shipping_jpy": "1000",
                    "payment_fee_jpy": "0",
                },
                "overseas_price_jpy": "152000",
            }
        },
    )
    detail = build_sourcing_detail(
        candidate=candidate,
        rank=None,
        batch_id="b1",
        selling_estimate=Decimal("155000"),
        batch_result=batch_result,
    )
    labels = [label for label, _ in detail.sales_info]
    assert "販売予想根拠" in labels or "比較件数" in labels
    assert "データ期間" in labels or "販売データ" in labels or "総合リスク" in labels
    assert "輸入コスト詳細" in labels
    assert any("HIGH" in str(value) for _, value in detail.sales_info)


def test_trust_summary_from_profit_trace() -> None:
    summary = trust_summary_from_profit_trace(
        {
            "comparable_quality": {"quality": "SUSPECT", "publish_price": False},
            "new_market_validation": {"risk": "CRITICAL"},
        }
    )
    assert summary.overall_risk == TrustRisk.DANGER
