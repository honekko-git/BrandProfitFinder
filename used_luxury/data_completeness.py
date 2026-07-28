"""
Data completeness assessment for used luxury items.
"""

from models.accessory_info import AccessoryProfile
from models.authentication_info import AuthenticationInfo
from models.seller_info import ReturnPolicy, SellerDetails
from models.used_item_condition import UsedItemCondition
from models.used_item_defects import DefectProfile


COMPLETENESS_FIELDS: tuple[str, ...] = (
    "condition",
    "condition_description",
    "defects",
    "accessories",
    "authentication",
    "seller",
    "return_policy",
    "image",
    "model_number",
    "serial",
    "url",
)


def calculate_data_completeness(
    *,
    condition: UsedItemCondition,
    condition_raw: str,
    condition_description: str,
    defects: DefectProfile,
    accessories: AccessoryProfile,
    authentication: AuthenticationInfo,
    seller: SellerDetails,
    return_policy: ReturnPolicy,
    has_image: bool,
    has_model_number: bool,
    has_serial: bool,
    has_url: bool,
) -> float:
    """
    Calculate how complete the used item data is (0.0-1.0).

    Unknown fields reduce completeness; they are not treated as confirmed OK.

    Args:
        condition: Normalized condition.
        condition_raw: Raw condition text.
        condition_description: Free-text condition description.
        defects: Defect profile.
        accessories: Accessory profile.
        authentication: Authentication info.
        seller: Seller details.
        return_policy: Return policy.
        has_image: Whether image URL is present.
        has_model_number: Whether model number is present.
        has_serial: Whether serial info is present.
        has_url: Whether listing URL is present.

    Returns:
        Completeness ratio between 0.0 and 1.0.
    """
    checks = {
        "condition": condition != UsedItemCondition.UNKNOWN or bool(condition_raw.strip()),
        "condition_description": bool(condition_description.strip()),
        "defects": bool(defects.entries),
        "accessories": accessories.known_count() > 0,
        "authentication": authentication.status.value != "UNKNOWN",
        "seller": seller.seller_type.value != "UNKNOWN" or seller.seller_rating is not None,
        "return_policy": return_policy.return_accepted is not None,
        "image": has_image,
        "model_number": has_model_number,
        "serial": has_serial,
        "url": has_url,
    }
    present = sum(1 for value in checks.values() if value)
    return round(present / len(checks), 4)
