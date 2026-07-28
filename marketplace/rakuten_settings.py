"""
Rakuten Ichiba Item Search API configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class RakutenConfig:
    """Validated Rakuten Ichiba API settings."""

    application_id: str
    access_key: str
    affiliate_id: str
    base_url: str
    timeout_seconds: int
    max_retries: int
    hits: int
    sort: str
    enabled: bool
    demo_enabled: bool

    @classmethod
    def from_env(cls) -> "RakutenConfig":
        """
        Load Rakuten settings from application configuration.

        Returns:
            Validated settings instance.
        """
        return cls(
            application_id=settings.RAKUTEN_APPLICATION_ID,
            access_key=settings.RAKUTEN_ACCESS_KEY,
            affiliate_id=settings.RAKUTEN_AFFILIATE_ID,
            base_url=settings.RAKUTEN_API_BASE_URL,
            timeout_seconds=settings.RAKUTEN_API_TIMEOUT_SECONDS,
            max_retries=settings.RAKUTEN_API_MAX_RETRIES,
            hits=settings.RAKUTEN_API_HITS,
            sort=settings.RAKUTEN_API_SORT,
            enabled=settings.RAKUTEN_API_ENABLED,
            demo_enabled=settings.RAKUTEN_API_DEMO_ENABLED,
        )

    @property
    def is_configured(self) -> bool:
        """Return True when application ID and access key are available."""
        return bool(self.application_id.strip()) and bool(self.access_key.strip())

    @property
    def can_execute(self) -> bool:
        """Return True when live API calls are enabled and configured."""
        return self.enabled and self.is_configured

    @property
    def can_demo(self) -> bool:
        """Return True when demo mode is enabled."""
        return self.enabled and self.demo_enabled

    def validate_hits(self, hits: int | None) -> int:
        """
        Validate hits parameter within API limits (1-30).

        Args:
            hits: Requested hits value.

        Returns:
            Validated hits count.
        """
        value = hits if hits is not None else self.hits
        return max(1, min(30, value))

    def validate_page(self, page: int) -> int:
        """
        Validate page parameter within API limits (1-100).

        Args:
            page: Requested page number.

        Returns:
            Validated page number.
        """
        return max(1, min(100, page))
