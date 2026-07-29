"""Brand and category query resolution for discovery searches."""

from __future__ import annotations

from profit_discovery.category_catalog.models import BrandCategorySearchTarget, CategoryProfile


class BrandCategoryResolver:
    """Build supplier search queries from brand and category combinations."""

    def build_query(self, brand: str, category: str) -> str:
        """Combine one brand and one category into a search query."""
        return f"{brand.strip()} {category.strip()}"

    def resolve(
        self,
        brands: list[str],
        categories: list[CategoryProfile] | tuple[CategoryProfile, ...],
    ) -> tuple[BrandCategorySearchTarget, ...]:
        """Generate brand-category search targets for all applicable combinations."""
        targets: list[BrandCategorySearchTarget] = []
        for brand in brands:
            normalized_brand = brand.strip()
            for category in categories:
                if not category.enabled:
                    continue
                if category.target_brands and normalized_brand not in category.target_brands:
                    continue
                targets.append(
                    BrandCategorySearchTarget(
                        brand=normalized_brand,
                        category=category.name,
                        query=self.build_query(normalized_brand, category.name),
                    )
                )
        return tuple(targets)
