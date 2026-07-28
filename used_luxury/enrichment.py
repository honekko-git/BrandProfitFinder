"""
Build and enrich UsedItemDetails from raw data.
"""

from decimal import Decimal
from typing import Any

from models.seller_info import ReturnPolicy, SellerDetails, SellerType
from models.used_item_condition import UsedItemCondition
from models.used_item_details import UsedItemDetails
from used_luxury.accessory_normalizer import AccessoryNormalizer
from used_luxury.authentication_normalizer import AuthenticationNormalizer
from used_luxury.condition_normalizer import ConditionNormalizationResult, ConditionNormalizer
from used_luxury.condition_scorer import ConditionScorer
from used_luxury.data_completeness import calculate_data_completeness
from used_luxury.defect_normalizer import DefectNormalizer
from used_luxury.price_adjustment import PriceAdjustmentCalculator
from used_luxury.risk_evaluator import UsedItemRiskEvaluator


class UsedItemEnricher:
    """Build fully enriched UsedItemDetails from raw internal JSON."""

    def __init__(self) -> None:
        self._condition_normalizer = ConditionNormalizer()
        self._defect_normalizer = DefectNormalizer()
        self._accessory_normalizer = AccessoryNormalizer()
        self._auth_normalizer = AuthenticationNormalizer()
        self._scorer = ConditionScorer()
        self._risk_evaluator = UsedItemRiskEvaluator()
        self._price_adjustment = PriceAdjustmentCalculator()

    def enrich(
        self,
        raw: dict[str, Any],
        *,
        price_jpy: Decimal | None = None,
        shipping_unknown: bool = False,
        listing_url: str = "",
        image_url: str = "",
        model_number: str = "",
    ) -> UsedItemDetails:
        """
        Parse raw used item data and compute scores, risk, and adjustments.

        Args:
            raw: Raw used item section from internal JSON.
            price_jpy: Listing price for risk/adjustment context.
            shipping_unknown: Whether shipping is unknown.
            listing_url: Listing URL for completeness.
            image_url: Image URL for completeness.
            model_number: Model number for completeness.

        Returns:
            Enriched UsedItemDetails.
        """
        condition_block = raw.get("condition") if isinstance(raw.get("condition"), dict) else {}
        raw_condition = str(condition_block.get("raw") or "").strip()
        if not raw_condition and isinstance(raw.get("condition"), str):
            raw_condition = str(raw.get("condition")).strip()

        normalized_hint = condition_block.get("normalized")
        if normalized_hint:
            norm_result = ConditionNormalizationResult(
                normalized_condition=UsedItemCondition.from_value(str(normalized_hint)),
                raw_condition=raw_condition or str(normalized_hint),
                confidence=1.0,
                matched_rule="fixture_normalized",
            )
        else:
            norm_result = self._condition_normalizer.normalize(raw_condition)

        defects = self._defect_normalizer.normalize(
            raw.get("defects") if isinstance(raw.get("defects"), dict) else None
        )
        accessories = self._accessory_normalizer.normalize(
            raw.get("accessories") if isinstance(raw.get("accessories"), dict) else None
        )
        authentication = self._auth_normalizer.normalize(
            raw.get("authentication") if isinstance(raw.get("authentication"), dict) else None
        )
        seller = self._parse_seller(raw.get("seller") if isinstance(raw.get("seller"), dict) else None)
        return_policy = self._parse_return_policy(
            raw.get("return_policy") if isinstance(raw.get("return_policy"), dict) else None
        )

        description = str(condition_block.get("description") or raw.get("condition_description") or "").strip()
        serial = str(raw.get("serial_number") or raw.get("serial") or "").strip()

        completeness = calculate_data_completeness(
            condition=norm_result.normalized_condition,
            condition_raw=norm_result.raw_condition,
            condition_description=description,
            defects=defects,
            accessories=accessories,
            authentication=authentication,
            seller=seller,
            return_policy=return_policy,
            has_image=bool(image_url.strip()),
            has_model_number=bool(model_number.strip()),
            has_serial=bool(serial),
            has_url=bool(listing_url.strip()),
        )

        score_result = self._scorer.score(
            norm_result.normalized_condition,
            condition_confidence=norm_result.confidence,
            defects=defects,
            accessories=accessories,
            data_completeness=completeness,
        )

        warnings = list(norm_result.warnings) + list(authentication.warnings) + list(score_result.warnings)

        details = UsedItemDetails(
            condition=norm_result.normalized_condition,
            condition_raw=norm_result.raw_condition,
            condition_confidence=norm_result.confidence,
            condition_description=description,
            condition_score=score_result,
            defects=defects,
            accessories=accessories,
            authentication=authentication,
            seller_details=seller,
            return_policy=return_policy,
            accessory_completeness=accessories.completeness,
            data_completeness=completeness,
            warnings=warnings,
            metadata={"matched_rule": norm_result.matched_rule},
        )

        if price_jpy is not None:
            details.price_adjustment = self._price_adjustment.calculate(
                price_jpy,
                norm_result.normalized_condition,
                confidence=norm_result.confidence,
            )

        details.risk = self._risk_evaluator.evaluate(
            details,
            price_jpy=price_jpy,
            shipping_unknown=shipping_unknown,
            has_description=bool(description),
            has_serial=bool(serial),
        )

        return details

    @staticmethod
    def _parse_seller(raw: dict[str, object] | None) -> SellerDetails:
        if not raw:
            return SellerDetails()
        rating = raw.get("rating")
        review_count = raw.get("review_count")
        return SellerDetails(
            seller_type=SellerType.from_value(raw.get("type")),
            seller_rating=Decimal(str(rating)) if rating is not None else None,
            seller_review_count=int(review_count) if review_count is not None else None,
            seller_verified=raw.get("verified") if isinstance(raw.get("verified"), bool) else None,
            business_name=str(raw.get("business_name") or "").strip(),
            country=str(raw.get("country") or "").strip(),
        )

    @staticmethod
    def _parse_return_policy(raw: dict[str, object] | None) -> ReturnPolicy:
        if not raw:
            return ReturnPolicy()
        period = raw.get("period_days")
        accepted = raw.get("accepted")
        return ReturnPolicy(
            return_accepted=accepted if isinstance(accepted, bool) else None,
            return_period_days=int(period) if period is not None else None,
        )
