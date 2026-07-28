"""
Vestiaire Collective marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class VestiaireSettings:
    """Configuration for Vestiaire Collective integration (no live API in Phase 9)."""

    enabled: bool
    timeout_seconds: int
    page_size: int
    max_pages: int
    default_currency: str
    demo_fixture_path: str
    allow_unknown_currency: bool
    include_inactive: bool
    include_sold: bool

    @classmethod
    def from_env(cls) -> "VestiaireSettings":
        """Load Vestiaire settings from application configuration."""
        return cls(
            enabled=settings.VESTIAIRE_ENABLED,
            timeout_seconds=settings.VESTIAIRE_TIMEOUT_SECONDS,
            page_size=settings.VESTIAIRE_PAGE_SIZE,
            max_pages=settings.VESTIAIRE_MAX_PAGES,
            default_currency=settings.VESTIAIRE_DEFAULT_CURRENCY,
            demo_fixture_path=settings.VESTIAIRE_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.VESTIAIRE_ALLOW_UNKNOWN_CURRENCY,
            include_inactive=settings.VESTIAIRE_INCLUDE_INACTIVE,
            include_sold=settings.VESTIAIRE_INCLUDE_SOLD,
        )

    def validate_page_size(self, page_size: int | None) -> int:
        """Validate page size within supported limits (1-50)."""
        value = page_size if page_size is not None else self.page_size
        return max(1, min(50, value))

    def validate_page(self, page: int) -> int:
        """Validate page number within supported limits (1-100)."""
        return max(1, min(100, page))

    def validate_max_pages(self, max_pages: int | None) -> int:
        """Validate max pages within supported limits (1-20)."""
        value = max_pages if max_pages is not None else self.max_pages
        return max(1, min(20, value))
