"""Deterministic product identity foundation."""

from product_identity.adapter import ProductIdentityService
from product_identity.enums import IdentityComparisonLevel, IdentityConfidence, IdentityDecision
from product_identity.evaluator import ProductIdentityEvaluator
from product_identity.models import ProductIdentityProfile, ProductIdentityResult
from product_identity.policy import (
    decision_allows_comparison,
    decision_allows_comparison_result,
    is_authoritative_match,
    resolve_identity_decision,
)

__all__ = [
    "IdentityComparisonLevel",
    "IdentityConfidence",
    "IdentityDecision",
    "ProductIdentityEvaluator",
    "ProductIdentityProfile",
    "ProductIdentityResult",
    "ProductIdentityService",
    "decision_allows_comparison",
    "decision_allows_comparison_result",
    "is_authoritative_match",
    "resolve_identity_decision",
]
