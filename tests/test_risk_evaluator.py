"""Tests for used item risk evaluator."""

from decimal import Decimal

from models.accessory_info import AccessoryCompleteness, AccessoryProfile
from models.authentication_info import AuthenticationInfo, AuthenticationStatus
from models.seller_info import ReturnPolicy, SellerDetails, SellerType
from models.used_item_condition import UsedItemCondition
from models.used_item_defects import DefectEntry, DefectProfile, DefectSeverity, TriState
from models.used_item_details import UsedItemDetails
from models.used_item_risk import RiskFlag, RiskLevel
from used_luxury.risk_evaluator import UsedItemRiskEvaluator


def _details(**kwargs) -> UsedItemDetails:
    defaults = dict(
        condition=UsedItemCondition.VERY_GOOD,
        data_completeness=0.7,
        authentication=AuthenticationInfo(),
        seller_details=SellerDetails(),
        return_policy=ReturnPolicy(),
        defects=DefectProfile(),
        accessories=AccessoryProfile(),
    )
    defaults.update(kwargs)
    return UsedItemDetails(**defaults)


def test_unknown_authentication_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(
        _details(authentication=AuthenticationInfo(status=AuthenticationStatus.UNKNOWN))
    )
    assert RiskFlag.AUTHENTICITY_UNKNOWN in risk.flags
    assert "counterfeit" not in " ".join(risk.reasons).lower()


def test_authenticity_concern_not_counterfeit_claim() -> None:
    risk = UsedItemRiskEvaluator().evaluate(
        _details(authentication=AuthenticationInfo(status=AuthenticationStatus.AUTHENTICITY_CONCERN))
    )
    assert RiskFlag.AUTHENTICITY_CONCERN in risk.flags
    assert any("not declared counterfeit" in w for w in risk.warnings)


def test_unknown_condition_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(_details(condition=UsedItemCondition.UNKNOWN))
    assert RiskFlag.CONDITION_UNKNOWN in risk.flags


def test_major_damage_flag() -> None:
    defects = DefectProfile(entries={"cracks": DefectEntry(TriState.TRUE, DefectSeverity.MAJOR)})
    risk = UsedItemRiskEvaluator().evaluate(_details(defects=defects))
    assert RiskFlag.MAJOR_DAMAGE in risk.flags


def test_missing_accessories_flag() -> None:
    accessories = AccessoryProfile(completeness=AccessoryCompleteness.ITEM_ONLY)
    risk = UsedItemRiskEvaluator().evaluate(_details(accessories=accessories))
    assert RiskFlag.MISSING_ACCESSORIES in risk.flags


def test_no_returns_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(_details(return_policy=ReturnPolicy(return_accepted=False)))
    assert RiskFlag.NO_RETURNS in risk.flags


def test_private_seller_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(
        _details(seller_details=SellerDetails(seller_type=SellerType.PRIVATE_SELLER))
    )
    assert RiskFlag.PRIVATE_SELLER in risk.flags


def test_low_rating_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(
        _details(seller_details=SellerDetails(seller_rating=Decimal("2.5")))
    )
    assert RiskFlag.LOW_SELLER_RATING in risk.flags


def test_repair_history_flag() -> None:
    defects = DefectProfile(entries={"repair_history": DefectEntry(TriState.TRUE, DefectSeverity.MODERATE)})
    risk = UsedItemRiskEvaluator().evaluate(_details(defects=defects))
    assert RiskFlag.REPAIR_HISTORY in risk.flags


def test_for_parts_critical() -> None:
    risk = UsedItemRiskEvaluator().evaluate(_details(condition=UsedItemCondition.FOR_PARTS))
    assert RiskFlag.FOR_PARTS in risk.flags
    assert risk.level == RiskLevel.CRITICAL


def test_shipping_unknown_flag() -> None:
    risk = UsedItemRiskEvaluator().evaluate(_details(), shipping_unknown=True)
    assert RiskFlag.SHIPPING_UNKNOWN in risk.flags


def test_combined_risk_level() -> None:
    defects = DefectProfile(entries={"cracks": DefectEntry(TriState.TRUE, DefectSeverity.CRITICAL)})
    risk = UsedItemRiskEvaluator().evaluate(
        _details(
            condition=UsedItemCondition.UNKNOWN,
            defects=defects,
            authentication=AuthenticationInfo(status=AuthenticationStatus.UNKNOWN),
            return_policy=ReturnPolicy(return_accepted=False),
        ),
        shipping_unknown=True,
    )
    assert risk.level in {RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.MEDIUM}
