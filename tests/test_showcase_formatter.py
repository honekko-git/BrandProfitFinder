"""Tests for showcase dashboard formatter."""

from __future__ import annotations

from decimal import Decimal

from models.price_result import PriceResult
from models.product import Product
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult, DiscoveryCandidateStatus
from profit_discovery.models import BuyDecision, BuyDecisionResult
from profit_discovery.multi_brand.models import MultiBrandDiscoveryResult
from profit_discovery.opportunity.models import DemandIntegratedOpportunityResult, DemandIntegratedOpportunityScore
from profit_discovery.showcase import ShowcaseFormatter
from profit_intelligence.demand.models import SalesDemandProfile
from supplier.models import SupplierProduct, SupplierType


def test_showcase_formatter_formats_top_ranking() -> None:
    opportunities = [_opportunity(rank=1, profit_jpy=35000, roi="42.0", demand_score=92.0, total_score=94.5)]

    rendered = ShowcaseFormatter().format_top_opportunities(opportunities)

    assert "AI PROFIT DISCOVERY SHOWCASE" in rendered
    assert "TOP OPPORTUNITIES" in rendered
    assert "Product:" in rendered
    assert "Chanel Wallet" in rendered
    assert "Brand:" in rendered
    assert "Chanel" in rendered
    assert "Supplier:" in rendered
    assert "Fashionphile" in rendered
    assert "35,000 JPY" in rendered
    assert "42%" in rendered
    assert "92/100" in rendered
    assert "94.5" in rendered
    assert "Decision:" in rendered
    assert "BUY" in rendered


def test_showcase_formatter_formats_summary_counts() -> None:
    result = MultiBrandDiscoveryResult(
        results=(),
        ranked_candidates=(
            _candidate(decision=BuyDecision.BUY),
            _candidate(decision=BuyDecision.HOLD),
            _candidate(decision=BuyDecision.PASS),
        ),
        ranked_opportunities=(),
        successful_brands=("Chanel",),
        failed_brands=(),
        total_candidates=3,
    )

    rendered = ShowcaseFormatter().format_summary(result)

    assert "Summary:" in rendered
    assert "Total Candidates:" in rendered
    assert "3" in rendered
    assert "BUY:" in rendered
    assert "1" in rendered
    assert "HOLD:" in rendered
    assert "PASS:" in rendered


def _opportunity(
    *,
    rank: int,
    profit_jpy: int,
    roi: str,
    demand_score: float,
    total_score: float,
) -> DemandIntegratedOpportunityResult:
    candidate = _candidate(decision=BuyDecision.BUY, profit_jpy=profit_jpy, roi=roi)
    return DemandIntegratedOpportunityResult(
        candidate=candidate,
        demand_profile=SalesDemandProfile(
            query="Chanel Wallet",
            period_days=30,
            sold_count=35,
            average_sold_price_jpy=160000.0,
            sell_through_rate=0.75,
            demand_score=demand_score,
        ),
        score=DemandIntegratedOpportunityScore(
            profit_score=80.0,
            margin_score=70.0,
            roi_score=75.0,
            market_confidence_score=60.0,
            supplier_score=90.0,
            demand_score=demand_score,
            total_score=total_score,
        ),
        recommendation_rank=rank,
    )


def _candidate(
    *,
    decision: BuyDecision,
    profit_jpy: int = 25000,
    roi: str = "35.0",
) -> DiscoveryCandidateResult:
    product = SupplierProduct(
        supplier_name="fashionphile",
        external_id="showcase-formatter-001",
        title="Chanel Classic Wallet",
        brand="Chanel",
        category="wallets",
        condition=SupplierType.USED.value,
        purchase_price=500.0,
        currency="USD",
        url="https://example.invalid/showcase-formatter-001",
        image_urls=[],
        availability="in_stock",
    )
    return DiscoveryCandidateResult(
        supplier_product=product,
        status=DiscoveryCandidateStatus.SUCCESS,
        profit_result=PriceResult(
            product=Product(name=product.title, brand=product.brand, price=500.0, currency="USD"),
            profit_jpy=Decimal(str(profit_jpy)),
            roi=Decimal(roi),
            calculation_status="success",
        ),
        buy_decision=BuyDecisionResult(
            decision=decision,
            max_purchase_price_jpy=Decimal("100000"),
            target_profit_jpy=Decimal("10000"),
            expected_profit_jpy=Decimal(str(profit_jpy)),
            margin_requirement=Decimal("20"),
        ),
    )
