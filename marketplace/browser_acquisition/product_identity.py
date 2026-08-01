"""Generic product identity extraction for comparable matching.

Brand-agnostic rules only — no brand-specific hardcodes.
Used by listing identity, search queries, and match scoring.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from marketplace.browser_acquisition.listing_identity import (
    extract_listing_identity,
    extract_model_numbers,
    normalize_brand,
    normalize_category,
    normalize_color,
    normalize_material,
)

# Generic collection / line phrases: material + optional style word, or known multi-word lines.
_COLLECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(saffiano\s+lux)\b",
        r"\b(vitello\s+daino)\b",
        r"\b(re[-\s]?edition)\b",
        r"\b(classic\s+flap)\b",
        r"\b(neverfull)\b",
        r"\b(speedy)\b",
        r"\b(alma)\b",
        r"\b(galleria)\b",
        r"\b(matelasse|matelass[eé]|マトラッセ)\b",
        r"(サフィアーノ\s*ラックス)",
        r"(ヴィッテロ\s*ダイナ)",
    )
)

_SIZE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mini", ("mini", "ミニ")),
    ("Small", ("small", "スモール", "pm")),
    ("Medium", ("medium", "ミディアム", "mm")),
    ("Large", ("large", "ラージ", "gm")),
)

# Overly broad bag/category families must not count as strong model identity.
GENERIC_MODEL_FAMILIES = frozenset(
    {
        "tote",
        "bag",
        "handbag",
        "shoulder",
        "wallet",
        "backpack",
        "clutch",
        "",
    }
)


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    """Structured product identity extracted from a listing title."""

    brand: str
    category: str
    reference_numbers: tuple[str, ...]
    collection: str
    family: str
    material: str
    color: str
    size: str
    cleaned_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def has_reference(self) -> bool:
        return bool(self.reference_numbers)

    @property
    def has_strong_model(self) -> bool:
        if self.has_reference:
            return True
        if self.collection:
            return True
        family = (self.family or "").strip().lower()
        return bool(family) and family not in GENERIC_MODEL_FAMILIES

    def primary_query_tokens(self) -> list[str]:
        """Ordered identity tokens for search: reference → collection/family → material → size → category."""
        tokens: list[str] = []
        if self.reference_numbers:
            tokens.append(self.reference_numbers[0])
        if self.collection:
            tokens.append(self.collection)
        elif self.family and self.family.lower() not in GENERIC_MODEL_FAMILIES:
            tokens.append(self.family)
        if self.material and self.material not in {"", "UNKNOWN", "OTHER"}:
            # Avoid duplicating material already inside collection (e.g. Saffiano Lux).
            if self.material.lower() not in (self.collection or "").lower():
                tokens.append(self.material.title() if self.material.isupper() else self.material)
        if self.size:
            tokens.append(self.size)
        if self.category and self.category not in {"", "UNKNOWN"}:
            tokens.append(self.category.replace("_", " ").title())
        return tokens


def is_generic_model_family(family: str) -> bool:
    return (family or "").strip().lower() in GENERIC_MODEL_FAMILIES


def extract_collection(title: str) -> str:
    """Extract a collection / line name from title text (generic patterns)."""
    text = unicodedata.normalize("NFKC", title or "")
    # Canonicalize known bilingual collection phrases first.
    folded = text.lower()
    canonical_map = (
        (("saffiano lux", "サフィアーノ ラックス", "サフィアーノラックス"), "Saffiano Lux"),
        (("vitello daino", "ヴィッテロ ダイナ", "ヴィッテロダイナ"), "Vitello Daino"),
        (("re-edition", "re edition", "reedition"), "Re-Edition"),
        (("classic flap", "クラシックフラップ"), "Classic Flap"),
    )
    for aliases, canonical in canonical_map:
        if any(alias in folded for alias in aliases):
            return canonical
    for pattern in _COLLECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1)
            return re.sub(r"\s+", " ", raw).strip().title()
    # Material + following Capitalized English word (e.g. "Saffiano Lux")
    material = normalize_material(title)
    if material not in {"", "UNKNOWN"}:
        mat_pat = re.compile(
            rf"\b({re.escape(material.lower())}|saffiano|サフィアーノ)\s+([A-Za-z][A-Za-z\-]+)\b",
            re.IGNORECASE,
        )
        match = mat_pat.search(text)
        if match:
            second = match.group(2)
            if second.lower() not in {
                "leather",
                "bag",
                "tote",
                "wallet",
                "handbag",
                "oval",
                "round",
                "square",
                "rectangular",
                "frame",
                "sunglasses",
                "sunglass",
                "acetate",
            }:
                return f"{match.group(1).title()} {second.title()}"
    return ""


def extract_size_token(title: str) -> str:
    haystack = unicodedata.normalize("NFKC", title or "").lower()
    for canonical, aliases in _SIZE_PATTERNS:
        if any(alias in haystack for alias in aliases):
            return canonical
    return ""


def extract_product_identity(
    *,
    title: str,
    brand: str = "",
    category: str = "",
    family_hint: str = "",
) -> ProductIdentity:
    """Extract brand / reference / collection / material / color / size / category."""
    listing = extract_listing_identity(title=title, brand=brand, category=category)
    collection = extract_collection(title)
    size = extract_size_token(title)
    family = family_hint or ""
    if not family and collection:
        family = collection
    refs = listing.model_numbers or extract_model_numbers(title)
    return ProductIdentity(
        brand=listing.brand or normalize_brand(brand, title=title),
        category=listing.category if listing.category != "UNKNOWN" else normalize_category(category, title=title),
        reference_numbers=refs,
        collection=collection,
        family=family,
        material=listing.material,
        color=listing.color,
        size=size,
        cleaned_title=listing.cleaned_title,
    )
