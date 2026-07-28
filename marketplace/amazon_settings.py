"""
Amazon.co.jp marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class AmazonConfig:
    """Configuration for Amazon.co.jp domestic marketplace integration."""

    marketplace_id: str
    default_currency: str
    default_language: str
    max_results: int
    timeout_seconds: int
    retry_count: int
    enabled: bool
    demo_enabled: bool

    @classmethod
    def from_env(cls) -> "AmazonConfig":
        """
        Load Amazon settings from application configuration.

        Returns:
            Validated Amazon configuration.
        """
        return cls(
            marketplace_id=settings.AMAZON_JP_MARKETPLACE_ID,
            default_currency=settings.AMAZON_JP_DEFAULT_CURRENCY,
            default_language=settings.AMAZON_JP_DEFAULT_LANGUAGE,
            max_results=settings.AMAZON_JP_MAX_RESULTS,
            timeout_seconds=settings.AMAZON_JP_TIMEOUT_SECONDS,
            retry_count=settings.AMAZON_JP_RETRY_COUNT,
            enabled=settings.AMAZON_JP_ENABLED,
            demo_enabled=settings.AMAZON_JP_DEMO_ENABLED,
        )

    @property
    def can_execute(self) -> bool:
        """Return True when Amazon search can run (demo or future live client)."""
        return self.enabled and self.demo_enabled
