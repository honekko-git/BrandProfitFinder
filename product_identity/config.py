"""Configuration for product identity evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from product_identity.enums import BroadCategory


@dataclass(frozen=True)
class CategoryPolicy:
    """Identity-defining fields for a broad category."""

    category: BroadCategory
    size_defines_variant: bool = False
    color_defines_variant: bool = False
    style_code_strong: bool = True
    reference_strong: bool = False


DEFAULT_CATEGORY_POLICIES: dict[BroadCategory, CategoryPolicy] = {
    BroadCategory.FOOTWEAR: CategoryPolicy(
        BroadCategory.FOOTWEAR,
        size_defines_variant=True,
        color_defines_variant=True,
        style_code_strong=True,
    ),
    BroadCategory.APPAREL: CategoryPolicy(
        BroadCategory.APPAREL,
        size_defines_variant=True,
        color_defines_variant=True,
        style_code_strong=True,
    ),
    BroadCategory.HANDBAG: CategoryPolicy(
        BroadCategory.HANDBAG,
        size_defines_variant=True,
        color_defines_variant=True,
        style_code_strong=True,
    ),
    BroadCategory.WATCH: CategoryPolicy(
        BroadCategory.WATCH,
        size_defines_variant=True,
        color_defines_variant=True,
        reference_strong=True,
    ),
    BroadCategory.COSMETICS: CategoryPolicy(
        BroadCategory.COSMETICS,
        size_defines_variant=True,
        color_defines_variant=True,
    ),
    BroadCategory.ACCESSORIES: CategoryPolicy(
        BroadCategory.ACCESSORIES,
        size_defines_variant=False,
        color_defines_variant=False,
    ),
    BroadCategory.GENERAL: CategoryPolicy(BroadCategory.GENERAL),
}


@dataclass(frozen=True)
class IdentityConfig:
    """Evaluator configuration."""

    title_overlap_review_threshold: float = 0.4
    title_overlap_informational_threshold: float = 0.2
    compatibility_score_cap: float = 100.0

    def policy_for(self, category: BroadCategory) -> CategoryPolicy:
        return DEFAULT_CATEGORY_POLICIES.get(category, DEFAULT_CATEGORY_POLICIES[BroadCategory.GENERAL])
