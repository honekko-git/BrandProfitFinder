"""Used luxury product mode configuration for domestic market discovery."""

from __future__ import annotations

from dataclasses import dataclass

from profit_discovery.category_catalog.models import CategoryProfile

USED_LUXURY_MARKETS: tuple[str, ...] = ("yahoo_auction", "mercari")
USED_LUXURY_CATEGORIES: tuple[str, ...] = ("wallet", "bag", "watch", "jewelry")

USED_LUXURY_HIGH_CATEGORIES: tuple[str, ...] = (
    "Wallet",
    "Classic Bag",
    "Shoulder Bag",
    "Mini Bag",
)
USED_LUXURY_MEDIUM_CATEGORIES: tuple[str, ...] = (
    "Watch",
    "Jewelry",
)
USED_LUXURY_LOW_CATEGORIES: tuple[str, ...] = (
    "Shoes",
    "Accessories",
)

USED_LUXURY_S_TIER_BRANDS: tuple[str, ...] = (
    "Chanel",
    "Louis Vuitton",
    "Hermes",
    "Miu Miu",
)
USED_LUXURY_A_TIER_BRANDS: tuple[str, ...] = (
    "Dior",
    "Celine",
    "Prada",
    "Loewe",
)
USED_LUXURY_B_TIER_BRANDS: tuple[str, ...] = (
    "Coach",
    "Bottega Veneta",
    "Fendi",
)

EXCLUDED_NEW_PRODUCT_MARKETS: tuple[str, ...] = (
    "amazon",
    "rakuten",
    "yahoo_shopping",
    "yahoo",
)


@dataclass(frozen=True, slots=True)
class UsedLuxuryModeConfig:
    """Configuration for used luxury brand discovery mode."""

    enabled: bool = True
    markets: tuple[str, ...] = USED_LUXURY_MARKETS
    categories: tuple[str, ...] = USED_LUXURY_CATEGORIES

    @classmethod
    def default(cls) -> UsedLuxuryModeConfig:
        """Return the default used luxury mode configuration."""
        return cls()

    def brand_names_for_tier(self, tier: str) -> list[str]:
        """Return used-luxury brand names for one tier."""
        normalized = tier.strip().upper()
        if normalized == "S":
            return list(USED_LUXURY_S_TIER_BRANDS)
        if normalized == "A":
            return list(USED_LUXURY_A_TIER_BRANDS)
        if normalized == "B":
            return list(USED_LUXURY_B_TIER_BRANDS)
        return []

    def all_brand_names(self) -> list[str]:
        """Return all supported used-luxury brand names."""
        return [
            *USED_LUXURY_S_TIER_BRANDS,
            *USED_LUXURY_A_TIER_BRANDS,
            *USED_LUXURY_B_TIER_BRANDS,
        ]

    def filter_brands(self, brands: list[str]) -> list[str]:
        """Keep only brands supported by used luxury mode."""
        allowed = {brand.lower() for brand in self.all_brand_names()}
        filtered: list[str] = []
        for brand in brands:
            if brand.strip().lower() in allowed:
                filtered.append(brand)
        return filtered

    def get_categories_by_priority(self, priority: str) -> tuple[str, ...]:
        """Return used-luxury category names for one priority band."""
        normalized = priority.strip().upper()
        if normalized == "HIGH":
            return USED_LUXURY_HIGH_CATEGORIES
        if normalized == "MEDIUM":
            return USED_LUXURY_MEDIUM_CATEGORIES
        if normalized == "LOW":
            return USED_LUXURY_LOW_CATEGORIES
        return ()

    def get_category_profiles_for_priority(self, priority: str) -> tuple[CategoryProfile, ...]:
        """Build category profiles for one used-luxury priority band."""
        return tuple(
            CategoryProfile(name=category, priority=priority.strip().upper())
            for category in self.get_categories_by_priority(priority)
        )

    def filter_categories(self, category_names: list[str]) -> list[str]:
        """Keep only categories supported by used luxury mode."""
        allowed = {category.lower() for category in self.categories}
        allowed.update(name.lower() for name in USED_LUXURY_HIGH_CATEGORIES)
        allowed.update(name.lower() for name in USED_LUXURY_MEDIUM_CATEGORIES)
        filtered: list[str] = []
        for category in category_names:
            normalized = category.strip().lower()
            if normalized in allowed or any(token in normalized for token in allowed):
                filtered.append(category)
        return filtered

    def market_display_names(self) -> tuple[str, ...]:
        """Return human-readable market names for CLI display."""
        return ("Yahoo Auction", "Mercari")

    def business_mode_label(self) -> str:
        """Return the showcase business mode label."""
        return "Used Luxury"

    def market_coverage_label(self) -> str:
        """Return the showcase market coverage label."""
        return "Yahoo Auction / Mercari"

    def is_excluded_market(self, market_name: str) -> bool:
        """Return True when a marketplace is outside used luxury scope."""
        normalized = market_name.strip().lower().replace(" ", "_")
        return normalized in EXCLUDED_NEW_PRODUCT_MARKETS
