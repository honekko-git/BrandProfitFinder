"""Enumerations for deterministic product identity evaluation."""

from __future__ import annotations

from enum import Enum


class IdentityDecision(str, Enum):
    """Explicit identity compatibility decision (not authenticity)."""

    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class IdentityConfidence(str, Enum):
    """Evidence strength tier; not a probability."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class IdentityComparisonLevel(str, Enum):
    """Comparison strictness for variant-sensitive categories."""

    PRODUCT_FAMILY = "PRODUCT_FAMILY"
    EXACT_VARIANT = "EXACT_VARIANT"


class IdentifierType(str, Enum):
    """Structured identifier kinds."""

    JAN = "JAN"
    EAN = "EAN"
    UPC = "UPC"
    GTIN = "GTIN"
    MPN = "MPN"
    SKU = "SKU"
    STYLE_CODE = "STYLE_CODE"
    MODEL_NUMBER = "MODEL_NUMBER"
    REFERENCE_NUMBER = "REFERENCE_NUMBER"
    PRODUCT_CODE = "PRODUCT_CODE"


class IdentifierScope(str, Enum):
    """Scope of an identifier value."""

    GLOBAL = "GLOBAL"
    MANUFACTURER = "MANUFACTURER"
    MARKETPLACE_LOCAL = "MARKETPLACE_LOCAL"
    UNKNOWN = "UNKNOWN"


class IdentifierSourceQuality(str, Enum):
    """Whether a value was explicit or inferred."""

    EXPLICIT = "EXPLICIT"
    METADATA = "METADATA"
    INFERRED = "INFERRED"


class EvidenceOutcome(str, Enum):
    """Pairwise evidence comparison outcome."""

    AGREE = "AGREE"
    CONFLICT = "CONFLICT"
    MISSING_LEFT = "MISSING_LEFT"
    MISSING_RIGHT = "MISSING_RIGHT"
    MISSING_BOTH = "MISSING_BOTH"
    INVALID_LEFT = "INVALID_LEFT"
    INVALID_RIGHT = "INVALID_RIGHT"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceStrength(str, Enum):
    """Relative weight of one evidence item."""

    STRONG = "STRONG"
    MEDIUM = "MEDIUM"
    WEAK = "WEAK"
    INFORMATIONAL = "INFORMATIONAL"


class BroadCategory(str, Enum):
    """Lightweight category policy selector."""

    FOOTWEAR = "footwear"
    APPAREL = "apparel"
    HANDBAG = "handbag"
    WATCH = "watch"
    COSMETICS = "cosmetics"
    ACCESSORIES = "accessories"
    GENERAL = "general"
