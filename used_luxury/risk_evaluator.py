"""
Risk evaluation for used luxury items.
"""

from decimal import Decimal

from models.accessory_info import AccessoryCompleteness, AccessoryProfile
from models.authentication_info import AuthenticationInfo, AuthenticationStatus
from models.seller_info import ReturnPolicy, SellerDetails, SellerType
from models.used_item_condition import UsedItemCondition
from models.used_item_defects import DefectProfile, TriState
from models.used_item_details import UsedItemDetails
from models.used_item_risk import RiskFlag, RiskLevel, UsedItemRisk


class UsedItemRiskEvaluator:
    """Evaluate resale risk for used luxury listings."""

    LOW_RATING_THRESHOLD = Decimal("3.5")

    def evaluate(
        self,
        details: UsedItemDetails,
        *,
        price_jpy: Decimal | None = None,
        shipping_unknown: bool = False,
        reference_price_jpy: Decimal | None = None,
        has_description: bool = True,
        model_matches: bool | None = None,
        has_serial: bool = False,
    ) -> UsedItemRisk:
        """
        Evaluate risk flags and overall level.

        Does not declare items counterfeit; flags authenticity unknown/concern only.

        Args:
            details: Used item details.
            price_jpy: Listing price.
            shipping_unknown: Whether shipping cost is unknown.
            reference_price_jpy: Optional reference price for outlier detection.
            has_description: Whether a condition description exists.
            model_matches: Whether model appears to match reference product.
            has_serial: Whether serial number is known.

        Returns:
            UsedItemRisk with level, flags, and reasons.
        """
        flags: list[RiskFlag] = []
        reasons: list[str] = []
        warnings: list[str] = []
        score = 0.0

        auth = details.authentication
        if auth.status in {AuthenticationStatus.UNKNOWN, AuthenticationStatus.NOT_AUTHENTICATED}:
            flags.append(RiskFlag.AUTHENTICITY_UNKNOWN)
            reasons.append("authentication status is unknown")
            score += 15
        elif auth.status == AuthenticationStatus.AUTHENTICITY_CONCERN:
            flags.append(RiskFlag.AUTHENTICITY_CONCERN)
            reasons.append("authenticity concern flagged")
            score += 30
            warnings.append("authenticity concern noted; not declared counterfeit")
        elif auth.status == AuthenticationStatus.SELLER_CLAIM_ONLY:
            flags.append(RiskFlag.AUTHENTICITY_UNKNOWN)
            reasons.append("only seller authenticity claim available")
            score += 10

        if details.condition in {UsedItemCondition.UNKNOWN, UsedItemCondition.USED_GENERIC}:
            flags.append(RiskFlag.CONDITION_UNKNOWN)
            reasons.append("condition rank is unknown or generic")
            score += 10

        if details.defects.has_major_damage():
            flags.append(RiskFlag.MAJOR_DAMAGE)
            reasons.append("major or critical damage reported")
            score += 25

        if details.accessories.completeness in {
            AccessoryCompleteness.ITEM_ONLY,
            AccessoryCompleteness.PARTIAL,
        }:
            flags.append(RiskFlag.MISSING_ACCESSORIES)
            reasons.append("accessories incomplete or item only")
            score += 8

        if details.return_policy.return_accepted is False:
            flags.append(RiskFlag.NO_RETURNS)
            reasons.append("returns not accepted")
            score += 10

        seller = details.seller_details
        if seller.seller_type == SellerType.PRIVATE_SELLER:
            flags.append(RiskFlag.PRIVATE_SELLER)
            reasons.append("private seller")
            score += 5

        if seller.seller_rating is not None and seller.seller_rating < self.LOW_RATING_THRESHOLD:
            flags.append(RiskFlag.LOW_SELLER_RATING)
            reasons.append(f"low seller rating: {seller.seller_rating}")
            score += 10

        if not has_description:
            flags.append(RiskFlag.INSUFFICIENT_DESCRIPTION)
            reasons.append("insufficient condition description")
            score += 8

        if self._has_repair_history(details.defects):
            flags.append(RiskFlag.REPAIR_HISTORY)
            reasons.append("repair history reported")
            score += 8

        if self._has_customization(details.defects):
            flags.append(RiskFlag.CUSTOMIZED_ITEM)
            reasons.append("customization reported")
            score += 8

        if details.condition == UsedItemCondition.FOR_PARTS:
            flags.append(RiskFlag.FOR_PARTS)
            reasons.append("item listed for parts")
            score += 30

        if shipping_unknown:
            flags.append(RiskFlag.SHIPPING_UNKNOWN)
            reasons.append("shipping cost unknown")
            score += 5

        if model_matches is False:
            flags.append(RiskFlag.MODEL_MISMATCH)
            reasons.append("model may not match reference product")
            score += 20

        if not has_serial:
            flags.append(RiskFlag.SERIAL_UNKNOWN)
            reasons.append("serial number unknown")
            score += 5

        if price_jpy is not None and reference_price_jpy is not None and reference_price_jpy > 0:
            ratio = float(price_jpy / reference_price_jpy)
            if ratio < 0.4:
                flags.append(RiskFlag.PRICE_TOO_LOW)
                reasons.append("price unusually low vs reference")
                score += 12
            elif ratio > 1.5:
                flags.append(RiskFlag.PRICE_TOO_HIGH)
                reasons.append("price unusually high vs reference")
                score += 8

        level = self._level_from_score(score, flags)
        confidence = details.data_completeness if details.data_completeness is not None else 0.3

        return UsedItemRisk(
            level=level,
            flags=flags,
            reasons=reasons,
            score=round(score, 2),
            confidence=round(confidence, 4),
            warnings=warnings,
        )

    @staticmethod
    def _has_repair_history(defects: DefectProfile) -> bool:
        entry = defects.get("repair_history")
        return entry.present == TriState.TRUE

    @staticmethod
    def _has_customization(defects: DefectProfile) -> bool:
        entry = defects.get("customization")
        return entry.present == TriState.TRUE

    @staticmethod
    def _level_from_score(score: float, flags: list[RiskFlag]) -> RiskLevel:
        if RiskFlag.AUTHENTICITY_CONCERN in flags or RiskFlag.FOR_PARTS in flags:
            return RiskLevel.CRITICAL
        if score >= 40:
            return RiskLevel.HIGH
        if score >= 20:
            return RiskLevel.MEDIUM
        if score > 0:
            return RiskLevel.LOW
        return RiskLevel.UNKNOWN
