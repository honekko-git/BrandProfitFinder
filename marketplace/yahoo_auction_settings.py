"""
Yahoo Auction marketplace configuration.
"""

from dataclasses import dataclass

from config import settings


@dataclass(frozen=True)
class YahooAuctionConfig:
    """Configuration for Yahoo Auction domestic marketplace integration."""

    enabled: bool
    demo_enabled: bool
    data_source: str
    timeout_seconds: int
    max_retries: int
    hits: int
    sort: str

    @classmethod
    def from_env(cls) -> "YahooAuctionConfig":
        """
        Load Yahoo Auction settings from application configuration.

        Returns:
            Validated settings instance.
        """
        return cls(
            enabled=settings.YAHOO_AUCTION_ENABLED,
            demo_enabled=settings.YAHOO_AUCTION_DEMO_ENABLED,
            data_source=settings.YAHOO_AUCTION_DATA_SOURCE,
            timeout_seconds=settings.YAHOO_AUCTION_TIMEOUT,
            max_retries=settings.YAHOO_AUCTION_MAX_RETRIES,
            hits=settings.YAHOO_AUCTION_HITS,
            sort=settings.YAHOO_AUCTION_SORT,
        )

    @property
    def has_live_data_source(self) -> bool:
        """Return True when a live data source identifier is configured."""
        return bool(self.data_source.strip())

    @property
    def can_demo(self) -> bool:
        """Return True when demo mode is enabled."""
        return self.enabled and self.demo_enabled

    @property
    def can_execute_live(self) -> bool:
        """Return True when live data execution is configured."""
        return self.enabled and self.has_live_data_source

    def validate_hits(self, hits: int | None) -> int:
        """
        Validate hits parameter within supported limits.

        Args:
            hits: Requested hits value.

        Returns:
            Validated hits count (1-30).
        """
        value = hits if hits is not None else self.hits
        return max(1, min(30, value))

    def validate_page(self, page: int) -> int:
        """
        Validate page parameter within supported limits.

        Args:
            page: Requested page number.

        Returns:
            Validated page number (1-100).
        """
        return max(1, min(100, page))
