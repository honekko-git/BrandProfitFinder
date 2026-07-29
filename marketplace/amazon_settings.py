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
    access_key: str = ""
    secret_key: str = ""
    partner_tag: str = ""
    region: str = "us-west-2"
    api_host: str = "webservices.amazon.co.jp"
    use_transport: bool = False

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
            access_key=settings.AMAZON_ACCESS_KEY,
            secret_key=settings.AMAZON_SECRET_KEY,
            partner_tag=settings.AMAZON_PARTNER_TAG,
            region=settings.AMAZON_REGION,
            api_host=settings.AMAZON_API_HOST,
            use_transport=settings.AMAZON_USE_TRANSPORT,
        )

    @property
    def is_configured(self) -> bool:
        """Return True when live Amazon API credentials are available."""
        return (
            bool(self.access_key.strip())
            and bool(self.secret_key.strip())
            and bool(self.partner_tag.strip())
        )

    @property
    def can_execute(self) -> bool:
        """Return True when Amazon search can run (demo or future live client)."""
        return self.enabled and self.demo_enabled
