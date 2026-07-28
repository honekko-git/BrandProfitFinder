"""Product identity data models."""

from __future__ import annotations

from dataclasses import dataclass, field

from product_identity.enums import (
    BroadCategory,
    EvidenceOutcome,
    EvidenceStrength,
    IdentityComparisonLevel,
    IdentityConfidence,
    IdentityDecision,
    IdentifierScope,
    IdentifierSourceQuality,
    IdentifierType,
)


@dataclass(frozen=True)
class NormalizedIdentifier:
    """One structured identifier value with provenance."""

    identifier_type: IdentifierType
    original_value: str
    normalized_value: str | None
    source_field: str
    source_marketplace: str = ""
    scope: IdentifierScope = IdentifierScope.UNKNOWN
    source_quality: IdentifierSourceQuality = IdentifierSourceQuality.EXPLICIT
    is_valid: bool = True


@dataclass
class ProductIdentityProfile:
    """Normalized identity attributes for one product or listing side."""

    marketplace: str = ""
    listing_id: str = ""
    brand: str | None = None
    model_name: str | None = None
    product_name: str | None = None
    category: BroadCategory = BroadCategory.GENERAL
    jan: str | None = None
    ean: str | None = None
    upc: str | None = None
    gtin: str | None = None
    mpn: str | None = None
    style_code: str | None = None
    model_number: str | None = None
    reference_number: str | None = None
    product_code: str | None = None
    color: str | None = None
    size_value: str | None = None
    size_system: str | None = None
    variant: str | None = None
    condition: str | None = None
    structured_identifiers: tuple[NormalizedIdentifier, ...] = ()
    source_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityEvidence:
    """One explainable identity evidence item."""

    field: str
    evidence_type: str
    left_original: str | None
    right_original: str | None
    left_normalized: str | None
    right_normalized: str | None
    outcome: EvidenceOutcome
    strength: EvidenceStrength
    explanation: str
    hard_conflict: bool = False
    source_quality: IdentifierSourceQuality = IdentifierSourceQuality.EXPLICIT


@dataclass(frozen=True)
class ProductIdentityResult:
    """Identity evaluation output for one product/listing pair."""

    decision: IdentityDecision
    confidence: IdentityConfidence
    comparison_level: IdentityComparisonLevel
    identity_score: float | None
    hard_conflict: bool
    review_required: bool
    family_compatible: bool | None
    exact_variant_confirmed: bool | None
    matched_fields: tuple[str, ...] = ()
    conflicting_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    evidence: tuple[IdentityEvidence, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def identity_decision(self) -> IdentityDecision:
        """Compatibility alias."""
        return self.decision

    @property
    def identity_confidence(self) -> IdentityConfidence:
        """Compatibility alias."""
        return self.confidence
