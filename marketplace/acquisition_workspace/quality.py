"""Candidate quality scoring and eligibility."""

from __future__ import annotations

import re
from decimal import Decimal

from marketplace.acquisition_workspace.models import CandidateQualityGrade
from marketplace.acquisition_workspace.normalization import is_supported_currency, is_valid_price

HARD_EXCLUSIONS = (
    "replica",
    "fake",
    "counterfeit",
    "box only",
    "parts only",
    "for parts",
    "箱のみ",
    "部品のみ",
    "レプリカ",
)

# Canonical normalized categories only (see normalize_category).
# Bag is the minimum handbag expansion; do not add raw taxonomy labels here.
SUPPORTED_LIVE_CATEGORIES = {"Wallet", "Bag"}


def score_candidate(
    *,
    title: str,
    brand: str,
    category: str,
    detected_subtype: str,
    detected_material: str,
    purchase_price: Decimal,
    currency: str,
    purchase_url: str,
    detected_condition: str,
) -> tuple[int, str, tuple[str, ...], tuple[str, ...], bool]:
    """Return quality score, grade, warnings, errors, eligible."""
    warnings: list[str] = []
    errors: list[str] = []
    score = 0

    if title.strip():
        score += 15 if len(title.strip()) >= 8 else 8
    else:
        errors.append("missing title")

    if brand:
        score += 10
    else:
        warnings.append("brand not detected")

    if category and category != "Unknown":
        score += 10
    else:
        warnings.append("category not detected")

    if detected_subtype and detected_subtype != "UNKNOWN":
        score += 15
    else:
        warnings.append("subtype unknown")

    if detected_material and detected_material != "Unknown":
        score += 10
    else:
        warnings.append("material unknown")

    if is_valid_price(purchase_price):
        score += 15
    else:
        errors.append("invalid purchase price")

    if is_supported_currency(currency):
        score += 10
    else:
        errors.append("unsupported currency")

    if purchase_url.strip().startswith(("http://", "https://")):
        score += 10
    else:
        errors.append("invalid purchase URL")

    if detected_condition and detected_condition != "UNKNOWN":
        score += 5

    lowered = title.lower()
    if any(token in lowered for token in HARD_EXCLUSIONS):
        errors.append("hard exclusion keyword")

    if category and category not in SUPPORTED_LIVE_CATEGORIES:
        warnings.append("CATEGORY_NOT_SUPPORTED_FOR_LIVE_PROFIT")

    if errors:
        grade = CandidateQualityGrade.REJECTED.value
        eligible = False
    else:
        grade = _grade_from_score(score)
        eligible = grade in {
            CandidateQualityGrade.A.value,
            CandidateQualityGrade.B.value,
            CandidateQualityGrade.C.value,
        } and brand != "" and category in SUPPORTED_LIVE_CATEGORIES

    return score, grade, tuple(warnings), tuple(errors), eligible


def _grade_from_score(score: int) -> str:
    if score >= 85:
        return CandidateQualityGrade.A.value
    if score >= 70:
        return CandidateQualityGrade.B.value
    if score >= 50:
        return CandidateQualityGrade.C.value
    return CandidateQualityGrade.REJECTED.value
