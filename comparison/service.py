"""
Cross-marketplace comparison orchestration service.
"""

from __future__ import annotations

import copy
import logging
from decimal import Decimal

from comparison.config import ComparisonConfig
from comparison.currency_safety import (
    authoritative_jpy_sale_price,
    is_jpy_comparable_listing,
    listing_source_price_amount,
    resolve_listing_currency,
)
from comparison.engine import ComparisonEngine
from comparison.matcher import ComparisonIdentityMatcher
from comparison.models import ComparisonRunResult, MarketplaceCandidate, ProductComparisonResult
from comparison.ranking import rank_comparison_results
from comparison.util import stable_unique
from marketplace.base_marketplace import BaseMarketplace
from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_UNKNOWN_CURRENCY, PriceResult
from models.product import Product
from price_compare.marketplace_profit_service import (
    _attach_used_item_metadata,
    calculate_profit_from_search_result,
)
from price_compare.profit_calculator import ProfitCalculator
from profit_intelligence.service import ProfitIntelligenceService, log_intelligence_summary

logger = logging.getLogger(__name__)


class CrossMarketplaceComparisonService:
    """Compare multiple marketplaces for the same products."""

    def __init__(
        self,
        config: ComparisonConfig | None = None,
        engine: ComparisonEngine | None = None,
    ) -> None:
        self.config = config or ComparisonConfig()
        self.engine = engine or ComparisonEngine(config=self.config)
        self._identity_matcher = ComparisonIdentityMatcher()

    def compare_products(
        self,
        products: list[Product],
        marketplaces: list[BaseMarketplace],
        calculator: ProfitCalculator,
        *,
        profit_intelligence: bool = False,
        expected_marketplaces: list[str] | None = None,
    ) -> ComparisonRunResult:
        """
        Search each marketplace for each product and build comparison summaries.

        Does not mutate input products or marketplace instances.
        """
        if not products:
            return ComparisonRunResult(metadata={"marketplace_count": len(marketplaces)})

        expected = expected_marketplaces or list(self.config.expected_marketplaces)
        if not expected:
            expected = [marketplace.marketplace_name for marketplace in marketplaces]

        all_search_results: list[MarketplaceSearchResult] = []
        all_listings: list[MarketplaceListing] = []
        pending: list[tuple[Product, list[MarketplaceCandidate]]] = []

        for product in products:
            candidates = self._search_marketplaces(
                product,
                marketplaces,
                calculator,
                start_index=len(all_search_results),
            )
            all_search_results.extend(candidate.search_result for candidate in candidates)
            for candidate in candidates:
                all_listings.extend(candidate.search_result.listings)
            pending.append((product, candidates))

        if profit_intelligence:
            self._apply_profit_intelligence_to_pending(pending)

        product_comparisons: list[ProductComparisonResult] = []
        run_warnings: list[str] = []
        for product, candidates in pending:
            comparison = self.engine.compare_product(
                product,
                candidates,
                expected_marketplaces=expected,
            )
            product_comparisons.append(comparison)
            run_warnings.extend(comparison.warnings)

        ranked = rank_comparison_results(product_comparisons)
        if profit_intelligence:
            log_intelligence_summary(ranked)

        logger.info(
            "Cross-marketplace comparison completed: products=%d marketplaces=%d comparisons=%d comparable=%d",
            len(products),
            len(marketplaces),
            len(product_comparisons),
            sum(item.comparable_count for item in product_comparisons),
        )
        return ComparisonRunResult(
            products=product_comparisons,
            all_search_results=all_search_results,
            all_listings=all_listings,
            ranked_price_results=ranked,
            warnings=stable_unique(run_warnings),
            metadata={
                "marketplace_count": len(marketplaces),
                "product_count": len(products),
                "profit_intelligence": profit_intelligence,
            },
        )

    def _search_marketplaces(
        self,
        product: Product,
        marketplaces: list[BaseMarketplace],
        calculator: ProfitCalculator,
        *,
        start_index: int,
    ) -> list[MarketplaceCandidate]:
        candidates: list[MarketplaceCandidate] = []
        for order_index, marketplace in enumerate(marketplaces):
            search_result = marketplace.search(product)
            listing = _select_identity_listing(
                product,
                search_result,
                self._identity_matcher,
                self.config.min_match_score,
            )
            identity_result = None
            if listing is not None:
                _eligible, _score, _warnings, identity_result = self._identity_matcher.evaluate_with_identity(
                    product,
                    listing,
                    min_score=self.config.min_match_score,
                )
            price_result = _build_price_result(
                product,
                listing,
                search_result,
                marketplace.marketplace_name,
                calculator,
            )
            currency = resolve_listing_currency(listing)
            source_amount = listing_source_price_amount(listing)
            jpy_comparable = is_jpy_comparable_listing(listing) and price_result.is_valid

            enriched = copy.deepcopy(price_result)
            metadata = dict(enriched.metadata or {})
            metadata["source_count"] = 0
            if currency is not None:
                metadata["source_currency"] = currency
            if source_amount is not None:
                metadata["source_price_amount"] = str(source_amount)
            metadata["jpy_comparable"] = jpy_comparable
            enriched.metadata = metadata

            candidates.append(
                MarketplaceCandidate(
                    marketplace_name=marketplace.marketplace_name,
                    search_result=search_result,
                    price_result=enriched,
                    order_index=start_index + order_index,
                    identity_listing=listing,
                    listing_currency=currency,
                    source_price_amount=source_amount,
                    jpy_comparable=jpy_comparable,
                    identity_result=identity_result,
                )
            )

        comparable_sources = sum(1 for candidate in candidates if candidate.is_comparable)
        for candidate in candidates:
            metadata = dict(candidate.price_result.metadata or {})
            metadata["source_count"] = comparable_sources
            candidate.price_result.metadata = metadata
        return candidates

    def _apply_profit_intelligence_to_pending(
        self,
        pending: list[tuple[Product, list[MarketplaceCandidate]]],
    ) -> None:
        service = ProfitIntelligenceService()
        for _product, candidates in pending:
            price_results = [candidate.price_result for candidate in candidates]
            related_search = [candidate.search_result for candidate in candidates]
            scored = service.score_results(price_results, related_search)
            for candidate, scored_result in zip(candidates, scored, strict=True):
                candidate.price_result = scored_result


def _build_price_result(
    product: Product,
    listing: MarketplaceListing | None,
    search_result: MarketplaceSearchResult,
    marketplace_name: str,
    calculator: ProfitCalculator,
) -> PriceResult:
    """Build profit result using authoritative JPY inputs only."""
    if listing is None:
        return calculate_profit_from_search_result(search_result, calculator)

    currency = resolve_listing_currency(listing)
    source_amount = listing_source_price_amount(listing)
    jpy_price = authoritative_jpy_sale_price(listing)

    if jpy_price is not None and jpy_price > 0:
        price_result = calculator.calculate(product, jpy_price, marketplace_name)
        _attach_used_item_metadata(price_result, listing)
        return price_result

    if currency is not None and currency != "JPY":
        return PriceResult(
            product=product,
            calculation_status=CALCULATION_UNKNOWN_CURRENCY,
            error_message=(
                f"non-JPY currency {currency}; no authoritative JPY conversion applied"
            ),
            domestic_market=marketplace_name,
            metadata={
                "source_currency": currency,
                "source_price_amount": str(source_amount) if source_amount is not None else None,
                "jpy_comparable": False,
            },
        )

    return calculate_profit_from_search_result(search_result, calculator)


def _select_identity_listing(
    product: Product,
    search_result: MarketplaceSearchResult,
    identity_matcher: ComparisonIdentityMatcher,
    min_score: Decimal,
) -> MarketplaceListing | None:
    """Pick the highest-scoring listing that passes identity matching."""
    candidates = list(search_result.valid_listings)
    if search_result.selected_listing is not None:
        selected = search_result.selected_listing
        if selected not in candidates:
            candidates.insert(0, selected)

    best_listing: MarketplaceListing | None = None
    best_score: Decimal | None = None
    for listing in candidates:
        eligible, score, _warnings, identity_result = identity_matcher.evaluate_with_identity(
            product,
            listing,
            min_score=min_score,
        )
        if identity_result is not None and identity_result.decision.value == "NO_MATCH":
            continue
        if not eligible or score is None:
            continue
        if best_score is None or score > best_score:
            best_listing = listing
            best_score = score
    return best_listing
