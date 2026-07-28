"""
Application-wide constants.

No business logic — fixed values used across modules.
"""

from typing import Final

# Supported overseas store identifiers
STORE_CETTIRE: Final[str] = "Cettire"
STORE_BALTINI: Final[str] = "Baltini"
STORE_ITALIST: Final[str] = "Italist"

SUPPORTED_STORES: Final[tuple[str, ...]] = (
    STORE_CETTIRE,
    STORE_BALTINI,
    STORE_ITALIST,
)

# Default currencies by region
CURRENCY_USD: Final[str] = "USD"
CURRENCY_EUR: Final[str] = "EUR"
CURRENCY_JPY: Final[str] = "JPY"

# Store base URLs
CETTIRE_BASE_URL: Final[str] = "https://www.cettire.com"
BALTINI_BASE_URL: Final[str] = "https://www.baltini.com"
ITALIST_BASE_URL: Final[str] = "https://www.italist.com"

# Store countries
COUNTRY_US: Final[str] = "US"
COUNTRY_IT: Final[str] = "IT"

# Excel sheet names
SHEET_PROFIT_RANKING: Final[str] = "Profit Ranking"
SHEET_BRAND_RANKING: Final[str] = "Brand Ranking"
SHEET_ROI_RANKING: Final[str] = "ROI Ranking"

# Default scan limit
DEFAULT_SCAN_LIMIT: Final[int] = 50

# Domestic marketplace identifiers
MARKETPLACE_LOCAL: Final[str] = "local"
MARKETPLACE_RAKUTEN: Final[str] = "rakuten"
MARKETPLACE_YAHOO: Final[str] = "yahoo"
MARKETPLACE_YAHOO_AUCTION: Final[str] = "yahoo_auction"
MARKETPLACE_MERCARI: Final[str] = "mercari"
MARKETPLACE_AMAZON_JP: Final[str] = "amazon_jp"
MARKETPLACE_VESTIAIRE: Final[str] = "vestiaire"
MARKETPLACE_FASHIONPHILE: Final[str] = "fashionphile"
MARKETPLACE_THEREALREAL: Final[str] = "therealreal"
MARKETPLACE_GRAILED: Final[str] = "grailed"
MARKETPLACE_CHRONO24: Final[str] = "chrono24"
MARKETPLACE_FARFETCH: Final[str] = "farfetch"
MARKETPLACE_STOCKX: Final[str] = "stockx"
MARKETPLACE_GOAT: Final[str] = "goat"
MARKETPLACE_USED_DEMO: Final[str] = "used_demo"

SHEET_DOMESTIC_LISTINGS: Final[str] = "Domestic Listings"
SHEET_MARKETPLACE_COMPARISON: Final[str] = "Marketplace Comparison"
