"""
Farfetch marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class FarfetchSettings:
    """Configuration for Farfetch integration (no live API in Phase 14)."""

    enabled: bool
    timeout_seconds: int
    page_size: int
    max_pages: int
    default_currency: str
    demo_fixture_path: str
    allow_unknown_currency: bool
    include_unavailable: bool
    include_sold: bool
    include_reserved: bool
    include_discounted_only: bool
    include_full_price_only: bool
    include_low_stock: bool
    include_final_sale: bool
    include_partner_boutiques: bool
    include_platform_inventory: bool
    require_known_shipping: bool
    require_known_duties: bool

    @classmethod
    def from_env(cls) -> "FarfetchSettings":
        """Load Farfetch settings from application configuration."""
        return cls(
            enabled=settings.FARFETCH_ENABLED,
            timeout_seconds=settings.FARFETCH_TIMEOUT_SECONDS,
            page_size=settings.FARFETCH_PAGE_SIZE,
            max_pages=settings.FARFETCH_MAX_PAGES,
            default_currency=settings.FARFETCH_DEFAULT_CURRENCY.strip().upper(),
            demo_fixture_path=settings.FARFETCH_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.FARFETCH_ALLOW_UNKNOWN_CURRENCY,
            include_unavailable=settings.FARFETCH_INCLUDE_UNAVAILABLE,
            include_sold=settings.FARFETCH_INCLUDE_SOLD,
            include_reserved=settings.FARFETCH_INCLUDE_RESERVED,
            include_discounted_only=settings.FARFETCH_INCLUDE_DISCOUNTED_ONLY,
            include_full_price_only=settings.FARFETCH_INCLUDE_FULL_PRICE_ONLY,
            include_low_stock=settings.FARFETCH_INCLUDE_LOW_STOCK,
            include_final_sale=settings.FARFETCH_INCLUDE_FINAL_SALE,
            include_partner_boutiques=settings.FARFETCH_INCLUDE_PARTNER_BOUTIQUES,
            include_platform_inventory=settings.FARFETCH_INCLUDE_PLATFORM_INVENTORY,
            require_known_shipping=settings.FARFETCH_REQUIRE_KNOWN_SHIPPING,
            require_known_duties=settings.FARFETCH_REQUIRE_KNOWN_DUTIES,
        )

    def validate_page_size(self, page_size: int | None) -> int:
        value = page_size if page_size is not None else self.page_size
        if value <= 0:
            return max(1, self.page_size)
        return max(1, min(50, value))

    def validate_page(self, page: int) -> int:
        return max(1, min(100, page))

    def validate_max_pages(self, max_pages: int | None) -> int:
        value = max_pages if max_pages is not None else self.max_pages
        if value <= 0:
            return max(1, self.max_pages)
        return max(1, min(20, value))

    def effective_price_filters(self) -> tuple[bool, bool, list[str]]:
        """
        Resolve discounted-only and full-price-only filters.

        When both are enabled, discounted-only takes precedence.
        """
        warnings: list[str] = []
        discounted = self.include_discounted_only
        full_price = self.include_full_price_only
        if discounted and full_price:
            warnings.append("include_discounted_only and include_full_price_only conflict; using discounted only")
            full_price = False
        return discounted, full_price, warnings
