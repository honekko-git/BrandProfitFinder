"""
Fashionphile marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class FashionphileSettings:
    """Configuration for Fashionphile integration (no live API in Phase 10)."""

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

    @classmethod
    def from_env(cls) -> "FashionphileSettings":
        """Load Fashionphile settings from application configuration."""
        return cls(
            enabled=settings.FASHIONPHILE_ENABLED,
            timeout_seconds=settings.FASHIONPHILE_TIMEOUT_SECONDS,
            page_size=settings.FASHIONPHILE_PAGE_SIZE,
            max_pages=settings.FASHIONPHILE_MAX_PAGES,
            default_currency=settings.FASHIONPHILE_DEFAULT_CURRENCY,
            demo_fixture_path=settings.FASHIONPHILE_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.FASHIONPHILE_ALLOW_UNKNOWN_CURRENCY,
            include_unavailable=settings.FASHIONPHILE_INCLUDE_UNAVAILABLE,
            include_sold=settings.FASHIONPHILE_INCLUDE_SOLD,
            include_reserved=settings.FASHIONPHILE_INCLUDE_RESERVED,
            include_discounted_only=settings.FASHIONPHILE_INCLUDE_DISCOUNTED_ONLY,
        )

    def validate_page_size(self, page_size: int | None) -> int:
        """Validate page size within supported limits (1-50)."""
        value = page_size if page_size is not None else self.page_size
        if value <= 0:
            return max(1, self.page_size)
        return max(1, min(50, value))

    def validate_page(self, page: int) -> int:
        """Validate page number within supported limits (1-100)."""
        return max(1, min(100, page))

    def validate_max_pages(self, max_pages: int | None) -> int:
        """Validate max pages within supported limits (1-20)."""
        value = max_pages if max_pages is not None else self.max_pages
        if value <= 0:
            return max(1, self.max_pages)
        return max(1, min(20, value))
