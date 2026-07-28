"""Collect explainable identity evidence between two profiles."""

from __future__ import annotations

from product_identity.enums import (
    EvidenceOutcome,
    EvidenceStrength,
    IdentifierType,
)
from product_identity.models import IdentityEvidence, ProductIdentityProfile
from product_identity.normalization import normalize_brand, normalize_code, normalize_color, title_overlap_ratio

EVIDENCE_FIELD_ORDER: tuple[str, ...] = (
    "gtin",
    "jan",
    "ean",
    "upc",
    "reference_number",
    "model_number",
    "style_code",
    "brand",
    "category",
    "variant",
    "size",
    "color",
    "product_name",
    "title_similarity",
)


def collect_evidence(
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
) -> tuple[IdentityEvidence, ...]:
    """Collect deterministic pairwise evidence."""
    items: list[IdentityEvidence] = []

    items.extend(_compare_global_identifiers(left, right))
    items.extend(_compare_simple_field("brand", left.brand, right.brand, EvidenceStrength.MEDIUM, hard_on_conflict=True))
    items.extend(
        _compare_simple_field(
            "model_number",
            left.model_number,
            right.model_number,
            EvidenceStrength.STRONG,
            hard_on_conflict=True,
        )
    )
    items.extend(
        _compare_simple_field(
            "style_code",
            left.style_code,
            right.style_code,
            EvidenceStrength.STRONG,
            hard_on_conflict=True,
        )
    )
    items.extend(
        _compare_simple_field(
            "reference_number",
            left.reference_number,
            right.reference_number,
            EvidenceStrength.STRONG,
            hard_on_conflict=True,
        )
    )
    items.extend(_compare_variant_fields(left, right))
    items.extend(_compare_title(left, right))

    order_map = {name: index for index, name in enumerate(EVIDENCE_FIELD_ORDER)}
    items.sort(key=lambda item: (order_map.get(item.field, 99), item.field))
    return tuple(items)


def _compare_global_identifiers(
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
) -> list[IdentityEvidence]:
    evidence: list[IdentityEvidence] = []
    left_map = _valid_identifier_map(left)
    right_map = _valid_identifier_map(right)
    for identifier_type in (
        IdentifierType.GTIN,
        IdentifierType.JAN,
        IdentifierType.EAN,
        IdentifierType.UPC,
    ):
        field = identifier_type.value.lower()
        left_value = left_map.get(identifier_type)
        right_value = right_map.get(identifier_type)
        if left_value is None and right_value is None:
            continue
        if left_value is None:
            evidence.append(
                IdentityEvidence(
                    field=field,
                    evidence_type=identifier_type.value,
                    left_original=None,
                    right_original=right_value.original_value,
                    left_normalized=None,
                    right_normalized=right_value.normalized_value,
                    outcome=EvidenceOutcome.MISSING_LEFT,
                    strength=EvidenceStrength.STRONG,
                    explanation="global identifier present only on listing side",
                )
            )
            continue
        if right_value is None:
            evidence.append(
                IdentityEvidence(
                    field=field,
                    evidence_type=identifier_type.value,
                    left_original=left_value.original_value,
                    right_original=None,
                    left_normalized=left_value.normalized_value,
                    right_normalized=None,
                    outcome=EvidenceOutcome.MISSING_RIGHT,
                    strength=EvidenceStrength.STRONG,
                    explanation="global identifier present only on product side",
                )
            )
            continue
        if not left_value.is_valid or not right_value.is_valid:
            outcome = EvidenceOutcome.INVALID_LEFT if not left_value.is_valid else EvidenceOutcome.INVALID_RIGHT
            evidence.append(
                IdentityEvidence(
                    field=field,
                    evidence_type=identifier_type.value,
                    left_original=left_value.original_value,
                    right_original=right_value.original_value,
                    left_normalized=left_value.normalized_value,
                    right_normalized=right_value.normalized_value,
                    outcome=outcome,
                    strength=EvidenceStrength.STRONG,
                    explanation="malformed global identifier",
                )
            )
            continue
        agree = left_value.normalized_value == right_value.normalized_value
        evidence.append(
            IdentityEvidence(
                field=field,
                evidence_type=identifier_type.value,
                left_original=left_value.original_value,
                right_original=right_value.original_value,
                left_normalized=left_value.normalized_value,
                right_normalized=right_value.normalized_value,
                outcome=EvidenceOutcome.AGREE if agree else EvidenceOutcome.CONFLICT,
                strength=EvidenceStrength.STRONG,
                explanation="global identifier agreement" if agree else "global identifier conflict",
                hard_conflict=not agree,
            )
        )
    return evidence


def _valid_identifier_map(profile: ProductIdentityProfile) -> dict:
    from product_identity.models import NormalizedIdentifier

    mapping: dict[IdentifierType, NormalizedIdentifier] = {}
    for item in profile.structured_identifiers:
        if item.identifier_type not in mapping:
            mapping[item.identifier_type] = item
    return mapping


def _compare_simple_field(
    field: str,
    left: str | None,
    right: str | None,
    strength: EvidenceStrength,
    *,
    hard_on_conflict: bool,
) -> list[IdentityEvidence]:
    left_norm = normalize_code(left) if field != "brand" else normalize_brand(left)
    right_norm = normalize_code(right) if field != "brand" else normalize_brand(right)
    if left_norm is None and right_norm is None:
        return []
    if left_norm is None:
        return [
            IdentityEvidence(
                field=field,
                evidence_type=field,
                left_original=left,
                right_original=right,
                left_normalized=None,
                right_normalized=right_norm,
                outcome=EvidenceOutcome.MISSING_LEFT,
                strength=strength,
                explanation=f"{field} present only on listing side",
            )
        ]
    if right_norm is None:
        return [
            IdentityEvidence(
                field=field,
                evidence_type=field,
                left_original=left,
                right_original=right,
                left_normalized=left_norm,
                right_normalized=None,
                outcome=EvidenceOutcome.MISSING_RIGHT,
                strength=strength,
                explanation=f"{field} present only on product side",
            )
        ]
    agree = left_norm == right_norm
    return [
        IdentityEvidence(
            field=field,
            evidence_type=field,
            left_original=left,
            right_original=right,
            left_normalized=left_norm,
            right_normalized=right_norm,
            outcome=EvidenceOutcome.AGREE if agree else EvidenceOutcome.CONFLICT,
            strength=strength,
            explanation=f"{field} agreement" if agree else f"{field} conflict",
            hard_conflict=hard_on_conflict and not agree,
        )
    ]


def _compare_variant_fields(
    left: ProductIdentityProfile,
    right: ProductIdentityProfile,
) -> list[IdentityEvidence]:
    evidence: list[IdentityEvidence] = []
    evidence.extend(
        _compare_simple_field("color", left.color, right.color, EvidenceStrength.MEDIUM, hard_on_conflict=True)
    )
    if left.size_value is None and right.size_value is None:
        return evidence
    same_system = (
        left.size_system is not None
        and right.size_system is not None
        and left.size_system == right.size_system
    )
    if left.size_value and right.size_value and same_system and left.size_value != right.size_value:
        evidence.append(
            IdentityEvidence(
                field="size",
                evidence_type="size",
                left_original=left.size_value,
                right_original=right.size_value,
                left_normalized=left.size_value,
                right_normalized=right.size_value,
                outcome=EvidenceOutcome.CONFLICT,
                strength=EvidenceStrength.STRONG,
                explanation="size conflict under known sizing system",
                hard_conflict=True,
            )
        )
    elif left.size_value and right.size_value and left.size_value == right.size_value:
        evidence.append(
            IdentityEvidence(
                field="size",
                evidence_type="size",
                left_original=left.size_value,
                right_original=right.size_value,
                left_normalized=left.size_value,
                right_normalized=right.size_value,
                outcome=EvidenceOutcome.AGREE,
                strength=EvidenceStrength.MEDIUM,
                explanation="size agreement",
            )
        )
    return evidence


def _compare_title(left: ProductIdentityProfile, right: ProductIdentityProfile) -> list[IdentityEvidence]:
    ratio = title_overlap_ratio(left.product_name, right.product_name)
    if ratio <= 0:
        return []
    strength = EvidenceStrength.WEAK if ratio >= 0.2 else EvidenceStrength.INFORMATIONAL
    return [
        IdentityEvidence(
            field="title_similarity",
            evidence_type="title",
            left_original=left.product_name,
            right_original=right.product_name,
            left_normalized=str(ratio),
            right_normalized=str(ratio),
            outcome=EvidenceOutcome.AGREE,
            strength=strength,
            explanation="deterministic title token overlap (weak evidence)",
        )
    ]
