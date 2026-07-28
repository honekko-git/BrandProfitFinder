"""Deterministic product identity foundation."""

from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityComparisonLevel, IdentityConfidence, IdentityDecision
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.models import ProductIdentityProfile, ProductIdentityResult

__all__ = [
    "IdentityComparisonLevel",
    "IdentityConfidence",
    "IdentityDecision",
    "ProductIdentityEvaluator",
    "ProductIdentityProfile",
    "ProductIdentityResult",
    "ProductIdentityService",
]
