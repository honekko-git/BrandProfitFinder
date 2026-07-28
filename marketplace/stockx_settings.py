"""
StockX marketplace configuration.
"""

from dataclasses import dataclass

from config import settings

_VALID_PRICE_SOURCES = frozenset({"LOWEST_ASK", "LAST_SALE", "NONE"})


@dataclass(frozen=True)
class StockXSettings:
    """Configuration for StockX integration (no live API in Phase 15)."""

    enabled: bool
    timeout_seconds: int
    page_size: int
    max_pages: int
    default_currency: str
    demo_fixture_path: str
    allow_unknown_currency: bool
    include_unavailable: bool
    include_sold: bool
    include_inactive: bool
    include_new: bool
    include_preowned: bool
    include_low_liquidity: bool
    require_known_lowest_ask: bool
    require_known_shipping: bool
    require_known_fees: bool
    minimum_sales_last_30_days: int
    minimum_asks_count: int
    minimum_bids_count: int
    maximum_volatility_rate: float | None
    preferred_price_source: str

    @classmethod
    def from_env(cls) -> "StockXSettings":
        """Load StockX settings from application configuration."""
        return cls(
            enabled=settings.STOCKX_ENABLED,
            timeout_seconds=settings.STOCKX_TIMEOUT_SECONDS,
            page_size=settings.STOCKX_PAGE_SIZE,
            max_pages=settings.STOCKX_MAX_PAGES,
            default_currency=settings.STOCKX_DEFAULT_CURRENCY.strip().upper(),
            demo_fixture_path=settings.STOCKX_DEMO_FIXTURE_PATH,
            allow_unknown_currency=settings.STOCKX_ALLOW_UNKNOWN_CURRENCY,
            include_unavailable=settings.STOCKX_INCLUDE_UNAVAILABLE,
            include_sold=settings.STOCKX_INCLUDE_SOLD,
            include_inactive=settings.STOCKX_INCLUDE_INACTIVE,
            include_new=settings.STOCKX_INCLUDE_NEW,
            include_preowned=settings.STOCKX_INCLUDE_PREOWNED,
            include_low_liquidity=settings.STOCKX_INCLUDE_LOW_LIQUIDITY,
            require_known_lowest_ask=settings.STOCKX_REQUIRE_KNOWN_LOWEST_ASK,
            require_known_shipping=settings.STOCKX_REQUIRE_KNOWN_SHIPPING,
            require_known_fees=settings.STOCKX_REQUIRE_KNOWN_FEES,
            minimum_sales_last_30_days=settings.STOCKX_MINIMUM_SALES_LAST_30_DAYS,
            minimum_asks_count=settings.STOCKX_MINIMUM_ASKS_COUNT,
            minimum_bids_count=settings.STOCKX_MINIMUM_BIDS_COUNT,
            maximum_volatility_rate=settings.STOCKX_MAXIMUM_VOLATILITY_RATE,
            preferred_price_source=cls.normalize_price_source(settings.STOCKX_PREFERRED_PRICE_SOURCE),
        )

    @staticmethod
    def normalize_price_source(value: str | None) -> str:
        text = str(value or "LOWEST_ASK").strip().upper().replace("-", "_").replace(" ", "_")
        if text not in _VALID_PRICE_SOURCES:
            return "LOWEST_ASK"
        return text

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
