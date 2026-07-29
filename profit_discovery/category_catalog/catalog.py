"""Category catalog for brand-category discovery targeting."""

from __future__ import annotations

from profit_discovery.category_catalog.models import CategoryPriority, CategoryProfile

DEFAULT_CATEGORY_PROFILES: tuple[CategoryProfile, ...] = (
    CategoryProfile(name="Wallet", priority=CategoryPriority.HIGH.value),
    CategoryProfile(name="Mini Bag", priority=CategoryPriority.HIGH.value),
    CategoryProfile(name="Shoulder Bag", priority=CategoryPriority.HIGH.value),
    CategoryProfile(name="Classic Bag", priority=CategoryPriority.HIGH.value),
    CategoryProfile(name="Vintage Bag", priority=CategoryPriority.HIGH.value),
    CategoryProfile(name="Watch", priority=CategoryPriority.MEDIUM.value),
    CategoryProfile(name="Jewelry", priority=CategoryPriority.MEDIUM.value),
    CategoryProfile(name="Shoes", priority=CategoryPriority.MEDIUM.value),
    CategoryProfile(name="Accessories", priority=CategoryPriority.MEDIUM.value),
    CategoryProfile(name="Clothing", priority=CategoryPriority.LOW.value),
)


class CategoryCatalog:
    """Manage discoverable product categories grouped by priority."""

    def __init__(self, categories: list[CategoryProfile] | None = None) -> None:
        self._categories = list(categories or DEFAULT_CATEGORY_PROFILES)

    @classmethod
    def default(cls) -> CategoryCatalog:
        """Return the default seeded category catalog."""
        return cls()

    def get_all_categories(self) -> tuple[CategoryProfile, ...]:
        """Return all catalog categories."""
        return tuple(self._categories)

    def get_high_priority_categories(self) -> tuple[CategoryProfile, ...]:
        """Return enabled high-priority categories."""
        return self.get_by_priority(CategoryPriority.HIGH.value)

    def get_by_priority(self, priority: str) -> tuple[CategoryProfile, ...]:
        """Return enabled categories that match the requested priority."""
        normalized = priority.strip().upper()
        return tuple(
            category
            for category in self._categories
            if category.enabled and category.priority.upper() == normalized
        )

    def get_for_brand(self, brand: str) -> tuple[CategoryProfile, ...]:
        """Return enabled categories applicable to one brand."""
        normalized = brand.strip()
        return tuple(
            category
            for category in self._categories
            if category.enabled
            and (not category.target_brands or normalized in category.target_brands)
        )

    def add_category(self, category: CategoryProfile) -> None:
        """Append one category profile to the catalog."""
        self._categories.append(category)
