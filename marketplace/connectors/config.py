"""Runtime configuration for market connector resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketConnectorConfig:
    """Runtime configuration for market connector resolution."""

    connector_mode: str = "FIXTURE"
    enable_live: bool = False
    use_fixture: bool = True
    fashionphile_api_url: str = ""
    yahoo_auction_api_url: str = ""
    timeout_seconds: float = 10.0
    retry_count: int = 2

    @classmethod
    def from_env(cls) -> MarketConnectorConfig:
        """Build connector config from environment variables."""
        mode = os.getenv("MARKET_CONNECTOR_MODE", "FIXTURE").strip().upper()
        return cls(
            connector_mode=mode,
            enable_live=mode == "LIVE",
            fashionphile_api_url=os.getenv("FASHIONPHILE_API_URL", "").strip(),
            yahoo_auction_api_url=os.getenv("YAHOO_AUCTION_API_URL", "").strip(),
        )

    def with_mode(self, market_mode: str) -> MarketConnectorConfig:
        """Return a copy configured for one browser market mode label."""
        normalized = market_mode.strip().upper()
        live = normalized == "LIVE"
        return MarketConnectorConfig(
            connector_mode=normalized if normalized in {"LIVE", "FIXTURE"} else self.connector_mode,
            enable_live=live,
            use_fixture=self.use_fixture,
            fashionphile_api_url=self.fashionphile_api_url,
            yahoo_auction_api_url=self.yahoo_auction_api_url,
            timeout_seconds=self.timeout_seconds,
            retry_count=self.retry_count,
        )
