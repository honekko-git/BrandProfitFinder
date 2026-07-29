"""Phase 25: comparison engine unification."""

from __future__ import annotations

from decimal import Decimal

from comparison.metadata.enricher import MetadataEnricher
from comparison.metadata.ranking_builder import (
    FOUNDATION_SCORE_KEY,
    IMPORT_COST_TOTAL_KEY,
    INTELLIGENCE_OVERALL_KEY,
    WARNING_COUNT_KEY,
)
from comparison.models import MarketplaceCandidate
from comparison.ranking import rank_candidates, rank_comparison_results
from comparison.ranking_adapter import ComparisonRankingAdapter
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from models.product import Product
from product_identity.enums import IdentityComparisonLevel, IdentityConfidence, IdentityDecision
from product_identity.models import ProductIdentityResult
from profit_intelligence.models import ProfitIntelligenceResult


def _candidate(
    marketplace: str,
    profit: Decimal,
    *,
    order_index: int,
    warnings: int = 0,
    completeness: float = 50,
    overall_score: int | None = None,
    identity_confidence: IdentityConfidence = IdentityConfidence.HIGH,
) -> MarketplaceCandidate:
    product = Product(name="Demo", brand="Demo", model="M", sku="S")
    search = MarketplaceSearchResult(
        product=product,
        marketplace_name=marketplace,
        selected_price_jpy=Decimal("10000"),
        metadata={"warnings": ["w"] * warnings},
    )
    price_result = PriceResult(
        product=product,
        profit_jpy=profit,
        profit_margin=Decimal("10"),
        roi=Decimal("5"),
        total_cost_jpy=Decimal("5000"),
        calculation_status=CALCULATION_SUCCESS,
        domestic_sale_price_jpy=Decimal("10000"),
        metadata={"data_completeness": completeness},
    )
    if overall_score is not None:
        price_result.profit_intelligence = ProfitIntelligenceResult(
            overall_score=float(overall_score),
            confidence_score=80.0,
            risk_score=20.0,
            profit_score=70.0,
            velocity_score=60.0,
            recommendation="Review",
            recommendation_stars=3,
        )
    identity_result = ProductIdentityResult(
        decision=IdentityDecision.MATCH,
        confidence=identity_confidence,
        comparison_level=IdentityComparisonLevel.EXACT_VARIANT,
        identity_score=90.0,
        hard_conflict=False,
        review_required=False,
        family_compatible=True,
        exact_variant_confirmed=True,
    )
    return MarketplaceCandidate(
        marketplace_name=marketplace,
        search_result=search,
        price_result=price_result,
        listing_currency="JPY",
        source_price_amount=Decimal("10000"),
        jpy_comparable=True,
        order_index=order_index,
        identity_result=identity_result,
    )


def test_metadata_enricher_populates_ranking_fields() -> None:
    candidate = _candidate("stockx", Decimal("1000"), order_index=0, overall_score=75)
    enriched = MetadataEnricher().enrich_candidates([candidate])[0]
    metadata = enriched.price_result.metadata or {}
    assert metadata.get("selected_review_identity_confidence") == "HIGH"
    assert metadata.get("identity_confidence_score") == "100"
    assert metadata.get(IMPORT_COST_TOTAL_KEY) == "5000"
    assert metadata.get(INTELLIGENCE_OVERALL_KEY) == 75.0
    assert metadata.get(FOUNDATION_SCORE_KEY) is not None
    assert enriched.price_result.ranking_score > Decimal("0")


def test_comparison_ranking_adapter_preserves_intelligence_first_order() -> None:
    lower_profit = _candidate("stockx", Decimal("1000"), order_index=0, overall_score=90)
    higher_profit = _candidate("goat", Decimal("5000"), order_index=1, overall_score=50)
    ranked = ComparisonRankingAdapter().rank_candidates([lower_profit, higher_profit])
    assert ranked[0].marketplace_name == "stockx"


def test_comparison_ranking_adapter_preserves_profit_over_completeness() -> None:
    low_profit = _candidate("stockx", Decimal("1000"), order_index=0, completeness=99)
    high_profit = _candidate("goat", Decimal("5000"), order_index=1, completeness=10)
    ranked = ComparisonRankingAdapter().rank_candidates([low_profit, high_profit])
    assert ranked[0].marketplace_name == "goat"


def test_rank_candidates_public_api_unchanged() -> None:
    candidates = [
        _candidate("a", Decimal("1000"), order_index=0),
        _candidate("b", Decimal("2000"), order_index=1, warnings=2),
    ]
    ranked = rank_candidates(candidates)
    assert ranked[0].marketplace_name == "b"


def test_rank_comparison_results_uses_enriched_metadata() -> None:
    from comparison.engine import ComparisonEngine

    product = Product(name="A", brand="B", model="M", sku="S")
    comparison = ComparisonEngine().compare_product(
        product,
        [
            _candidate("stockx", Decimal("1000"), order_index=0),
            _candidate("goat", Decimal("3000"), order_index=1),
        ],
    )
    ranked = rank_comparison_results([comparison])
    assert len(ranked) == 1
    assert ranked[0].profit_jpy == Decimal("3000")
    assert ranked[0].metadata.get(FOUNDATION_SCORE_KEY) is not None


def test_deterministic_repeated_enrichment() -> None:
    candidate = _candidate("stockx", Decimal("1000"), order_index=0)
    enricher = MetadataEnricher()
    first = enricher.enrich_candidates([candidate])[0].price_result.metadata
    second = enricher.enrich_candidates([candidate])[0].price_result.metadata
    assert first == second


def test_warning_count_metadata() -> None:
    candidate = _candidate("stockx", Decimal("1000"), order_index=0, warnings=3)
    enriched = MetadataEnricher().enrich_candidates([candidate])[0]
    assert enriched.price_result.metadata.get(WARNING_COUNT_KEY) == 3
