"""
Chrono24 marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class Chrono24Settings:
    """Configuration for Chrono24 integration (no live API in Phase 13)."""

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
    include_negotiable_only: bool
    include_discounted_only: bool
    require_verified_seller: bool
    require_trusted_seller: bool
    include_private_sellers: bool
    include_professional_dealers: bool

    @classmethod
    def from_env(cls) -> "Chrono24Settings":
        """Load Chrono24 settings from application configuration."""
        return cls(
            enabled=settings.CHRONO24_ENABLED,
            timeout_seconds=settings.CHRONO24_TIMEOUT_SECONDS,
            page_size=settings.CHRONO24_PAGE_SIZE,
            max_pages=settings.CHRONO24_MAX_PAGES,
            default_currency=settings.CHRONO24_DEFAULT_CURRENCY,
            demo_fixture_path=settings.CHRONO24_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.CHRONO24_ALLOW_UNKNOWN_CURRENCY,
            include_unavailable=settings.CHRONO24_INCLUDE_UNAVAILABLE,
            include_sold=settings.CHRONO24_INCLUDE_SOLD,
            include_reserved=settings.CHRONO24_INCLUDE_RESERVED,
            include_negotiable_only=settings.CHRONO24_INCLUDE_NEGOTIABLE_ONLY,
            include_discounted_only=settings.CHRONO24_INCLUDE_DISCOUNTED_ONLY,
            require_verified_seller=settings.CHRONO24_REQUIRE_VERIFIED_SELLER,
            require_trusted_seller=settings.CHRONO24_REQUIRE_TRUSTED_SELLER,
            include_private_sellers=settings.CHRONO24_INCLUDE_PRIVATE_SELLERS,
            include_professional_dealers=settings.CHRONO24_INCLUDE_PROFESSIONAL_DEALERS,
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
