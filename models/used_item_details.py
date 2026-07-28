"""
Aggregated used item details model.
"""

from dataclasses import dataclass, field
from typing import Any

from models.accessory_info import AccessoryCompleteness, AccessoryProfile
from models.authentication_info import AuthenticationInfo
from models.seller_info import ReturnPolicy, SellerDetails
from models.used_item_condition import UsedItemCondition
from models.used_item_defects import DefectProfile
from models.used_item_risk import UsedItemRisk


@dataclass
class ConditionScoreResult:
    """Condition score with supporting metadata."""

    score: int | None = None
    confidence: float | None = None
    deductions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_completeness: float | None = None


@dataclass
class PriceAdjustmentResult:
    """Suggested price adjustment based on condition (not auto-applied)."""

    original_price_jpy: float | None = None
    adjustment_rate: float | None = None
    adjustment_amount_jpy: float | None = None
    adjusted_price_jpy: float | None = None
    reasons: list[str] = field(default_factory=list)
    confidence: float | None = None
    applied: bool = False


@dataclass
class UsedItemDetails:
    """Site-independent used luxury item details."""

    condition: UsedItemCondition = UsedItemCondition.UNKNOWN
    condition_raw: str = ""
    condition_confidence: float | None = None
    condition_description: str = ""
    condition_score: ConditionScoreResult | None = None
    defects: DefectProfile = field(default_factory=DefectProfile)
    accessories: AccessoryProfile = field(default_factory=AccessoryProfile)
    authentication: AuthenticationInfo = field(default_factory=AuthenticationInfo)
    seller_details: SellerDetails = field(default_factory=SellerDetails)
    return_policy: ReturnPolicy = field(default_factory=ReturnPolicy)
    accessory_completeness: AccessoryCompleteness = AccessoryCompleteness.UNKNOWN
    data_completeness: float | None = None
    risk: UsedItemRisk | None = None
    price_adjustment: PriceAdjustmentResult | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def condition_score_value(self) -> int | None:
        """Return numeric condition score when available."""
        if self.condition_score is None:
            return None
        return self.condition_score.score

    @property
    def condition_score_confidence(self) -> float | None:
        """Return condition score confidence when available."""
        if self.condition_score is None:
            return None
        return self.condition_score.confidence

    @property
    def risk_level(self) -> str | None:
        """Return risk level string when evaluated."""
        if self.risk is None:
            return None
        return self.risk.level.value

    @property
    def risk_flags(self) -> list[str]:
        """Return risk flag names when evaluated."""
        if self.risk is None:
            return []
        return self.risk.flag_values()

    @property
    def risk_reasons(self) -> list[str]:
        """Return risk reasons when evaluated."""
        if self.risk is None:
            return []
        return list(self.risk.reasons)
