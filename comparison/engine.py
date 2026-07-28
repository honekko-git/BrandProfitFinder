"""
Cross-marketplace comparison engine.
"""

from __future__ import annotations

import copy

from comparison.config import ComparisonConfig
from comparison.currency_safety import (
    normalize_currency_code,
    resolve_listing_currency,
)
from comparison.matcher import ComparisonIdentityMatcher
from comparison.models import MarketplaceCandidate, ProductComparisonResult
from comparison.ranking import highest_profit_candidate, rank_candidates
from comparison.util import stable_unique
from config.constants import CURRENCY_JPY
from models.marketplace_listing import MarketplaceListing
from models.product import Product

RELIABILITY_HIGH = "high"
RELIABILITY_MEDIUM = "medium"
RELIABILITY_LOW = "low"
RELIABILITY_INSUFFICIENT = "insufficient"


class ComparisonEngine:
    """Build product-level comparison summaries from marketplace candidates."""

    def __init__(
        self,
        config: ComparisonConfig | None = None,
        identity_matcher: ComparisonIdentityMatcher | None = None,
    ) -> None:
        self.config = config or ComparisonConfig()
        self._identity_matcher = identity_matcher or ComparisonIdentityMatcher()

    def compare_product(
        self,
        product: Product,
        candidates: list[MarketplaceCandidate],
        *,
        expected_marketplaces: list[str] | None = None,
    ) -> ProductComparisonResult:
        """
        Compare marketplace candidates for one product.

        Args:
            product: Overseas product being evaluated.
            candidates: Marketplace outcomes in stable order.
            expected_marketplaces: Optional expected marketplace list.

        Returns:
            ProductComparisonResult with advisory metadata only.
        """
        filtered = self._filter_candidates(product, candidates)
        warnings = self._collect_run_warnings(filtered)
        currencies = self._observed_currencies(filtered)
        currency_consistent = self._currency_consistency(currencies, warnings)
        price_consistent = self._price_consistency(filtered, warnings)

        expected = list(expected_marketplaces or self.config.expected_marketplaces)
        supported = [candidate.marketplace_name for candidate in filtered if candidate.is_comparable]
        compared = [candidate.marketplace_name for candidate in filtered]
        missing = [name for name in expected if name not in compared]

        ranked = rank_candidates(filtered)
        selected = ranked[0] if ranked and ranked[0].is_comparable else None
        highest = highest_profit_candidate(filtered)

        result = ProductComparisonResult(
            product=product,
            candidates=filtered,
            selected_review_marketplace=selected.marketplace_name if selected else None,
            selected_review_profit_jpy=selected.comparable_profit_jpy if selected else None,
            selected_review_margin=selected.comparable_profit_margin if selected else None,
            highest_profit_marketplace=highest.marketplace_name if highest else None,
            highest_profit_jpy=highest.comparable_profit_jpy if highest else None,
            highest_profit_margin=highest.comparable_profit_margin if highest else None,
            supported_marketplaces=supported,
            missing_marketplaces=missing,
            currencies_observed=currencies,
            currency_consistent=currency_consistent,
            price_consistent=price_consistent,
            warnings=warnings,
            validation_summary=self._validation_summary(filtered),
            comparison_reliability=self._reliability(filtered, warnings, currency_consistent),
            recommendation=self._recommendation(selected, highest, filtered, warnings),
            metadata={
                "candidate_count": len(filtered),
                "comparable_count": len(supported),
            },
        )
        self._attach_intelligence_summary(result, filtered)
        return result

    def _filter_candidates(
        self,
        product: Product,
        candidates: list[MarketplaceCandidate],
    ) -> list[MarketplaceCandidate]:
        filtered: list[MarketplaceCandidate] = []
        for candidate in candidates:
            copy_candidate = self._copy_candidate(candidate)
            listing = copy_candidate.identity_listing or copy_candidate.search_result.selected_listing
            is_match, score, match_warnings = self._identity_matcher.evaluate(
                product,
                listing,
                min_score=self.config.min_match_score,
            )
            copy_candidate.match_score = score
            copy_candidate.match_warnings = list(match_warnings)
            copy_candidate.listing_currency = _candidate_currency(copy_candidate, listing)

            if self.config.require_identity_match and listing is not None and not is_match:
                copy_candidate.identity_matched = False
                copy_candidate.match_warnings.append(
                    "excluded from comparison due to weak identity match"
                )

            if not copy_candidate.jpy_comparable and copy_candidate.listing_currency not in {
                None,
                CURRENCY_JPY,
            }:
                copy_candidate.match_warnings.append(
                    f"non-JPY currency {copy_candidate.listing_currency}; "
                    "not JPY-comparable without authoritative conversion"
                )

            filtered.append(copy_candidate)
        return filtered

    @staticmethod
    def _copy_candidate(candidate: MarketplaceCandidate) -> MarketplaceCandidate:
        return MarketplaceCandidate(
            marketplace_name=candidate.marketplace_name,
            search_result=candidate.search_result,
            price_result=copy.deepcopy(candidate.price_result),
            match_score=candidate.match_score,
            match_warnings=list(candidate.match_warnings),
            listing_currency=candidate.listing_currency,
            source_price_amount=candidate.source_price_amount,
            jpy_comparable=candidate.jpy_comparable,
            order_index=candidate.order_index,
            identity_matched=candidate.identity_matched,
            identity_listing=candidate.identity_listing,
        )

    def _collect_run_warnings(self, candidates: list[MarketplaceCandidate]) -> list[str]:
        warnings: list[str] = []
        comparable = [candidate for candidate in candidates if candidate.is_comparable]
        if len(comparable) < 2:
            warnings.append("fewer than two comparable marketplace outcomes")

        currencies = {
            currency
            for candidate in candidates
            if (currency := candidate.listing_currency)
        }
        non_jpy = sorted({currency for currency in currencies if currency != CURRENCY_JPY})
        if len(currencies) > 1:
            warnings.append(
                "mixed currencies observed across marketplaces; no conversion applied"
            )
        if non_jpy:
            warnings.append(
                f"non-JPY currencies observed ({', '.join(non_jpy)}); "
                "profit comparison uses authoritative JPY results only"
            )

        seen_marketplaces: set[str] = set()
        for candidate in candidates:
            if candidate.marketplace_name in seen_marketplaces:
                warnings.append(f"duplicate marketplace outcome: {candidate.marketplace_name}")
            seen_marketplaces.add(candidate.marketplace_name)

        for candidate in candidates:
            if candidate.search_result.error_message:
                warnings.append(
                    f"{candidate.marketplace_name}: {candidate.search_result.error_message}"
                )
            warnings.extend(
                f"{candidate.marketplace_name}: {warning}"
                for warning in candidate.match_warnings
            )
        return stable_unique(warnings)

    @staticmethod
    def _observed_currencies(candidates: list[MarketplaceCandidate]) -> list[str]:
        currencies = [
            candidate.listing_currency
            for candidate in candidates
            if candidate.listing_currency
        ]
        return stable_unique(currencies)

    @staticmethod
    def _currency_consistency(
        currencies: list[str],
        warnings: list[str],
    ) -> bool | None:
        if not currencies:
            return None
        if len(set(currencies)) == 1:
            return True
        warnings.append("currency consistency check failed")
        return False

    @staticmethod
    def _price_consistency(
        candidates: list[MarketplaceCandidate],
        warnings: list[str],
    ) -> bool | None:
        prices = [
            candidate.source_price_amount
            for candidate in candidates
            if candidate.is_comparable and candidate.source_price_amount is not None
        ]
        if not prices:
            return None
        if len(set(prices)) == 1:
            return True
        return False

    @staticmethod
    def _validation_summary(candidates: list[MarketplaceCandidate]) -> str:
        valid = sum(1 for candidate in candidates if candidate.is_comparable)
        rejected = sum(len(candidate.search_result.rejected_listings) for candidate in candidates)
        return f"comparable={valid}; rejected_listings={rejected}"

    @staticmethod
    def _reliability(
        candidates: list[MarketplaceCandidate],
        warnings: list[str],
        currency_consistent: bool | None,
    ) -> str:
        comparable = [candidate for candidate in candidates if candidate.is_comparable]
        if not comparable:
            return RELIABILITY_INSUFFICIENT
        if len(comparable) == 1:
            return RELIABILITY_LOW
        if currency_consistent is False or any("weak identity match" in w for w in warnings):
            return RELIABILITY_MEDIUM
        if len(comparable) >= 2:
            return RELIABILITY_HIGH
        return RELIABILITY_MEDIUM

    @staticmethod
    def _recommendation(
        selected: MarketplaceCandidate | None,
        highest: MarketplaceCandidate | None,
        candidates: list[MarketplaceCandidate],
        warnings: list[str],
    ) -> str:
        comparable = [candidate for candidate in candidates if candidate.is_comparable]
        if not comparable:
            return "Review required: insufficient JPY-comparable marketplace data"
        if selected is None:
            return "Review required: no selected review candidate under current rules"
        selected_label = selected.marketplace_name
        if highest is not None and highest.marketplace_name != selected.marketplace_name:
            base = (
                f"Review candidate: {selected_label} selected under ranking policy; "
                f"highest observed JPY profit was {highest.marketplace_name}"
            )
        else:
            base = (
                f"Review candidate: {selected_label} selected under ranking policy "
                "for JPY-comparable results"
            )
        if warnings:
            return f"{base}; verify warnings before acting"
        return base

    @staticmethod
    def _attach_intelligence_summary(
        result: ProductComparisonResult,
        candidates: list[MarketplaceCandidate],
    ) -> None:
        for candidate in candidates:
            if not candidate.is_comparable:
                continue
            intel = candidate.price_result.profit_intelligence
            metadata = candidate.price_result.metadata or {}
            completeness = metadata.get("data_completeness")
            if completeness is not None:
                try:
                    value = float(completeness)
                except (TypeError, ValueError):
                    value = None
                if value is not None and (
                    result.best_data_completeness is None
                    or value > result.best_data_completeness
                ):
                    result.best_data_completeness = value
            if intel is None:
                continue
            if intel.confidence_score is not None and (
                result.best_confidence_score is None
                or intel.confidence_score > result.best_confidence_score
            ):
                result.best_confidence_score = intel.confidence_score
            if intel.risk_score is not None and (
                result.best_risk_score is None
                or intel.risk_score < result.best_risk_score
            ):
                result.best_risk_score = intel.risk_score
            if intel.overall_score is not None and (
                result.best_overall_score is None
                or intel.overall_score > result.best_overall_score
            ):
                result.best_overall_score = intel.overall_score


def _candidate_currency(
    candidate: MarketplaceCandidate,
    listing: MarketplaceListing | None,
) -> str | None:
    if candidate.listing_currency:
        return normalize_currency_code(candidate.listing_currency)
    return resolve_listing_currency(listing)
