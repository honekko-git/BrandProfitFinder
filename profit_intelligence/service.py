"""
Profit Intelligence service and input adapters.
"""

from __future__ import annotations

import copy
import logging
from decimal import Decimal
from typing import Any

from models.marketplace_listing import MarketplaceListing
from models.marketplace_search_result import MarketplaceSearchResult
from models.price_result import CALCULATION_SUCCESS, PriceResult
from profit_intelligence.confidence_scorer import ConfidenceScorer
from profit_intelligence.explanation_builder import ExplanationBuilder
from profit_intelligence.models import (
    ProfitIntelligenceInput,
    ProfitIntelligenceResult,
)
from profit_intelligence.normalization import (
    normalize_optional_decimal,
    normalize_optional_float,
    normalize_optional_int,
)
from profit_intelligence.profit_scorer import ProfitScorer
from profit_intelligence.recommendation_engine import RecommendationEngine
from profit_intelligence.risk_scorer import RiskScorer
from profit_intelligence.velocity_scorer import VelocityScorer

logger = logging.getLogger(__name__)


class ProfitIntelligenceService:
    """Normalize inputs, run scorers, and build intelligence results."""

    def __init__(self) -> None:
        self.profit_scorer = ProfitScorer()
        self.velocity_scorer = VelocityScorer()
        self.risk_scorer = RiskScorer()
        self.confidence_scorer = ConfidenceScorer()
        self.explanation_builder = ExplanationBuilder()
        self.recommendation_engine = RecommendationEngine()

    def score_input(self, data: ProfitIntelligenceInput) -> ProfitIntelligenceResult:
        profit = self.profit_scorer.score(data)
        velocity = self.velocity_scorer.score(data)
        risk = self.risk_scorer.score(data)
        confidence = self.confidence_scorer.score(data)

        components = {
            "profit": profit,
            "velocity": velocity,
            "risk": risk,
            "confidence": confidence,
        }
        reasons, warnings, missing = self.explanation_builder.build(components)

        return self.recommendation_engine.combine(
            profit,
            velocity,
            risk,
            confidence,
            reasons=reasons,
            warnings=warnings,
            missing_fields=missing,
        )

    def build_input(
        self,
        price_result: PriceResult,
        *,
        search_result: MarketplaceSearchResult | None = None,
        listing: MarketplaceListing | None = None,
    ) -> ProfitIntelligenceInput:
        selected = listing or (
            search_result.selected_listing if search_result is not None else None
        )
        metadata = self._merge_metadata(price_result, selected, search_result)

        profit_amount = normalize_optional_decimal(price_result.profit_jpy)
        margin_percent = normalize_optional_decimal(price_result.profit_margin)

        shipping_known = self._resolve_known_flag(
            metadata,
            "shipping_known",
            default=price_result.is_valid,
        )
        fees_known = self._resolve_known_flag(
            metadata,
            "fees_known",
            default=price_result.is_valid,
        )
        duties_known = self._resolve_known_flag(
            metadata,
            "duties_known",
            default=price_result.is_valid,
        )

        currency = self._safe_str(
            metadata.get("source_currency") or price_result.source_currency or price_result.currency
        )

        return ProfitIntelligenceInput(
            profit_amount_jpy=profit_amount,
            profit_margin_percent=margin_percent,
            domestic_sale_price_jpy=normalize_optional_decimal(price_result.domestic_sale_price_jpy),
            overseas_purchase_price_jpy=normalize_optional_decimal(price_result.purchase_price_jpy),
            currency=currency,
            shipping_cost_known=shipping_known,
            marketplace_fee_known=fees_known,
            duties_tax_known=duties_known,
            sales_last_30_days=normalize_optional_int(metadata.get("sales_last_30_days")),
            sales_last_72_hours=normalize_optional_int(metadata.get("sales_last_72_hours")),
            asks_count=normalize_optional_int(metadata.get("asks_count")),
            bids_count=normalize_optional_int(metadata.get("bids_count")),
            inventory_count=normalize_optional_int(metadata.get("inventory_count")),
            volatility_percent=normalize_optional_decimal(metadata.get("volatility_rate")),
            lowest_ask=normalize_optional_decimal(metadata.get("lowest_ask")),
            highest_bid=normalize_optional_decimal(metadata.get("highest_bid")),
            last_sale_price=normalize_optional_decimal(metadata.get("last_sale")),
            identifier_match_strength=normalize_optional_float(
                metadata.get("identifier_match_strength")
            ),
            title_match_strength=self._title_match_strength(selected, metadata),
            size_match=self._size_match(selected, metadata),
            style_code_present=self._identifier_present(metadata, "source_style_code"),
            product_id_present=self._identifier_present(metadata, "source_product_id"),
            jan_present=self._identifier_present(metadata, "source_jan"),
            source_count=normalize_optional_int(metadata.get("source_count")),
            listing_count=self._listing_count(search_result),
            rejected_listing_count=self._rejected_count(search_result),
            validation_warning_count=self._validation_warning_count(search_result, metadata),
        )

    def score_price_result(
        self,
        price_result: PriceResult,
        *,
        search_result: MarketplaceSearchResult | None = None,
        listing: MarketplaceListing | None = None,
    ) -> ProfitIntelligenceResult:
        data = self.build_input(price_result, search_result=search_result, listing=listing)
        return self.score_input(data)

    def score_results(
        self,
        results: list[PriceResult],
        search_results: list[MarketplaceSearchResult] | None = None,
    ) -> list[PriceResult]:
        """Return new PriceResult copies with profit_intelligence attached."""
        search_by_product: dict[str, MarketplaceSearchResult] = {}
        if search_results:
            for item in search_results:
                key = self._search_result_key(item)
                search_by_product[key] = item

        scored: list[PriceResult] = []
        for index, result in enumerate(results):
            search = None
            if search_results:
                key = self._result_key(result)
                search = search_by_product.get(key)
                if search is None and index < len(search_results):
                    search = search_results[index]

            clone = copy.deepcopy(result)
            clone.profit_intelligence = self.score_price_result(
                result,
                search_result=search,
            )
            scored.append(clone)
        return scored

    @staticmethod
    def _result_key(result: PriceResult) -> str:
        product = result.product
        if product is not None:
            return f"{product.sku}:{product.name}"
        return result.title or ""

    @staticmethod
    def _search_result_key(search_result: MarketplaceSearchResult) -> str:
        product = search_result.product
        if product is not None:
            return f"{product.sku}:{product.name}"
        return search_result.query or ""

    @staticmethod
    def _merge_metadata(
        price_result: PriceResult,
        listing: MarketplaceListing | None,
        search_result: MarketplaceSearchResult | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if price_result.metadata:
            merged.update(price_result.metadata)
        if listing is not None and listing.source_metadata:
            merged.update(listing.source_metadata)
        if search_result is not None and search_result.metadata:
            merged.update(search_result.metadata)
        if search_result is not None:
            for key in (
                "sales_last_30_days",
                "sales_last_72_hours",
                "asks_count",
                "bids_count",
                "inventory_count",
                "volatility_rate",
                "lowest_ask",
                "highest_bid",
                "last_sale",
            ):
                value = getattr(search_result, key, None)
                if value is not None:
                    merged.setdefault(key, value)
        return merged

    @staticmethod
    def _resolve_known_flag(
        metadata: dict[str, Any],
        key: str,
        *,
        default: bool | None,
    ) -> bool | None:
        if key in metadata:
            value = metadata[key]
            if isinstance(value, bool):
                return value
        return default

    @staticmethod
    def _optional_bool(value: Any) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _identifier_present(metadata: dict[str, Any], key: str) -> bool | None:
        if key not in metadata:
            return None
        value = metadata[key]
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)

    @staticmethod
    def _title_match_strength(
        listing: MarketplaceListing | None,
        metadata: dict[str, Any],
    ) -> float | None:
        if listing is not None and listing.match_score is not None:
            return normalize_optional_float(listing.match_score)
        return normalize_optional_float(metadata.get("title_match_strength"))

    @staticmethod
    def _size_match(
        listing: MarketplaceListing | None,
        metadata: dict[str, Any],
    ) -> bool | None:
        if "size_match" in metadata:
            return ProfitIntelligenceService._optional_bool(metadata.get("size_match"))
        if listing is not None and listing.source_metadata.get("size_match") is not None:
            return ProfitIntelligenceService._optional_bool(
                listing.source_metadata.get("size_match")
            )
        return None

    @staticmethod
    def _validation_warning_count(
        search_result: MarketplaceSearchResult | None,
        metadata: dict[str, Any],
    ) -> int | None:
        if "validation_warning_count" in metadata:
            return normalize_optional_int(metadata.get("validation_warning_count"))
        if search_result is None:
            return None
        return len(search_result.rejected_listings)

    @staticmethod
    def _listing_count(search_result: MarketplaceSearchResult | None) -> int | None:
        if search_result is None:
            return None
        return len(search_result.valid_listings)

    @staticmethod
    def _rejected_count(search_result: MarketplaceSearchResult | None) -> int | None:
        if search_result is None:
            return None
        rejected = len(search_result.listings) - len(search_result.valid_listings)
        return max(rejected, 0)


def rank_by_intelligence_score(
    results: list[PriceResult],
    *,
    exclude_invalid: bool = True,
) -> list[PriceResult]:
    """Rank by overall score desc, profit desc, stable original order."""
    indexed = list(enumerate(results))
    if exclude_invalid:
        indexed = [
            (index, result)
            for index, result in indexed
            if result.calculation_status == CALCULATION_SUCCESS
        ]

    def sort_key(item: tuple[int, PriceResult]) -> tuple:
        index, result = item
        intel = result.profit_intelligence
        overall = intel.overall_score if intel is not None else None
        profit = result.profit_jpy
        profit_value = float(profit) if profit is not None else float("-inf")
        overall_sort = overall if overall is not None else float("-inf")
        return (-overall_sort, -profit_value, index)

    return [item[1] for item in sorted(indexed, key=sort_key)]


def log_intelligence_summary(results: list[PriceResult]) -> None:
    total = len(results)
    complete = sum(
        1
        for item in results
        if item.profit_intelligence is not None
        and item.profit_intelligence.overall_score is not None
    )
    insufficient = total - complete
    logger.info(
        "Profit intelligence summary: scored=%d complete=%d insufficient=%d",
        total,
        complete,
        insufficient,
    )
