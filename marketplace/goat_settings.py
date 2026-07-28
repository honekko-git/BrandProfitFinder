"""
GOAT marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class GoatSettings:
    """Configuration for GOAT integration (no live API in Phase 17)."""

    enabled: bool
    timeout_seconds: int
    page_size: int
    max_pages: int
    default_currency: str
    demo_fixture_path: str
    allow_unknown_currency: bool
    include_unavailable: bool
    include_sold: bool
    include_new: bool
    include_used: bool
    require_known_price: bool

    @classmethod
    def from_env(cls) -> "GoatSettings":
        """Load GOAT settings from application configuration."""
        return cls(
            enabled=settings.GOAT_ENABLED,
            timeout_seconds=settings.GOAT_TIMEOUT_SECONDS,
            page_size=settings.GOAT_PAGE_SIZE,
            max_pages=settings.GOAT_MAX_PAGES,
            default_currency=settings.GOAT_DEFAULT_CURRENCY.strip().upper(),
            demo_fixture_path=settings.GOAT_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.GOAT_ALLOW_UNKNOWN_CURRENCY,
            include_unavailable=settings.GOAT_INCLUDE_UNAVAILABLE,
            include_sold=settings.GOAT_INCLUDE_SOLD,
            include_new=settings.GOAT_INCLUDE_NEW,
            include_used=settings.GOAT_INCLUDE_USED,
            require_known_price=settings.GOAT_REQUIRE_KNOWN_PRICE,
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
