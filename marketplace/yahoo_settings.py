"""
Yahoo Shopping API configuration helpers.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from config import settings


@dataclass(frozen=True)
class YahooApiSettings:
    """Validated Yahoo Shopping API settings."""

    client_id: str
    base_url: str
    timeout_seconds: int
    results: int
    enabled: bool

    @classmethod
    def from_env(cls) -> "YahooApiSettings":
        """
        Load Yahoo API settings from application configuration.

        Returns:
            Validated settings instance.
        """
        return cls(
            client_id=settings.YAHOO_CLIENT_ID,
            base_url=settings.YAHOO_API_BASE_URL,
            timeout_seconds=settings.YAHOO_API_TIMEOUT_SECONDS,
            results=settings.YAHOO_API_RESULTS,
            enabled=settings.YAHOO_API_ENABLED,
        )

    @property
    def is_configured(self) -> bool:
        """Return True when Client ID is available for API calls."""
        return bool(self.client_id.strip())

    @property
    def can_execute(self) -> bool:
        """Return True when API calls are enabled and configured."""
        return self.enabled and self.is_configured


def validate_yahoo_base_url(url: str) -> str:
    """
    Validate Yahoo API base URL format.

    Args:
        url: Candidate base URL.

    Returns:
        Normalized URL string.

    Raises:
        ValueError: When URL is invalid.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("invalid Yahoo API base URL")
    return url.strip()
