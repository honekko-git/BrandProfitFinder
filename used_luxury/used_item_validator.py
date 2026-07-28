"""
Optional validation for used item details on marketplace listings.
"""

from models.authentication_info import AuthenticationStatus
from models.used_item_details import UsedItemDetails


def validate_used_item_details(details: UsedItemDetails | None) -> tuple[bool, str]:
    """
    Validate optional used item details.

    Args:
        details: Used item details or None.

    Returns:
        Tuple of (is_valid, error_message). None details are always valid.
    """
    if details is None:
        return True, ""

    if details.condition_confidence is not None:
        if details.condition_confidence < 0.0 or details.condition_confidence > 1.0:
            return False, "condition_confidence must be between 0.0 and 1.0"

    if details.condition_score is not None:
        score = details.condition_score.score
        if score is not None and (score < 0 or score > 100):
            return False, "condition_score must be between 0 and 100"
        conf = details.condition_score.confidence
        if conf is not None and (conf < 0.0 or conf > 1.0):
            return False, "condition score confidence must be between 0.0 and 1.0"

    if details.data_completeness is not None:
        if details.data_completeness < 0.0 or details.data_completeness > 1.0:
            return False, "data_completeness must be between 0.0 and 1.0"

    if details.accessories.included_count() < 0:
        return False, "accessory included count must not be negative"

    if details.return_policy.return_period_days is not None:
        if details.return_policy.return_period_days < 0:
            return False, "return_period_days must not be negative"

    auth = details.authentication
    if auth.status == AuthenticationStatus.AUTHENTICATED:
        if not auth.platform_authenticated and not auth.third_party_authenticated:
            return False, "authenticated status requires platform or third-party confirmation"

    return True, ""
