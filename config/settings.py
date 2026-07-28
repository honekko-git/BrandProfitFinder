"""
Application settings.

Centralized configuration used throughout the project.
No business logic.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRY = int(os.getenv("MAX_RETRY", "3"))

USER_AGENT = os.getenv(
    "USER_AGENT",
    (
        "BrandProfitFinder/0.1 "
        "(compatible; research tool; +https://github.com/local/brand-profit-finder)"
    ),
)

DEFAULT_EXCHANGE_RATE = float(os.getenv("DEFAULT_EXCHANGE_RATE", "160.0"))

EXCEL_FILENAME = os.getenv("EXCEL_FILENAME", "profit_ranking.xlsx")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOG_DIR / "brand_profit_finder.log"

YAHOO_CLIENT_ID = os.getenv("YAHOO_CLIENT_ID", "").strip()
YAHOO_API_BASE_URL = os.getenv(
    "YAHOO_API_BASE_URL",
    "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch",
).strip()
YAHOO_API_TIMEOUT_SECONDS = max(1, int(os.getenv("YAHOO_API_TIMEOUT_SECONDS", "10")))
YAHOO_API_RESULTS = max(1, min(100, int(os.getenv("YAHOO_API_RESULTS", "20"))))
YAHOO_API_ENABLED = os.getenv("YAHOO_API_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

AMAZON_JP_MARKETPLACE_ID = os.getenv("AMAZON_JP_MARKETPLACE_ID", "A1VC38T7YXB528").strip()
AMAZON_JP_DEFAULT_CURRENCY = os.getenv("AMAZON_JP_DEFAULT_CURRENCY", "JPY").strip().upper()
AMAZON_JP_DEFAULT_LANGUAGE = os.getenv("AMAZON_JP_DEFAULT_LANGUAGE", "ja_JP").strip()
AMAZON_JP_MAX_RESULTS = max(1, min(100, int(os.getenv("AMAZON_JP_MAX_RESULTS", "20"))))
AMAZON_JP_TIMEOUT_SECONDS = max(1, int(os.getenv("AMAZON_JP_TIMEOUT_SECONDS", "10")))
AMAZON_JP_RETRY_COUNT = max(0, int(os.getenv("AMAZON_JP_RETRY_COUNT", "0")))
AMAZON_JP_ENABLED = os.getenv("AMAZON_JP_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
AMAZON_JP_DEMO_ENABLED = os.getenv("AMAZON_JP_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

RAKUTEN_APPLICATION_ID = os.getenv("RAKUTEN_APPLICATION_ID", "").strip()
RAKUTEN_ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()
RAKUTEN_API_BASE_URL = os.getenv(
    "RAKUTEN_API_BASE_URL",
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701",
).strip()
RAKUTEN_API_TIMEOUT_SECONDS = max(1, int(os.getenv("RAKUTEN_API_TIMEOUT_SECONDS", "10")))
RAKUTEN_API_MAX_RETRIES = max(0, int(os.getenv("RAKUTEN_API_MAX_RETRIES", "2")))
RAKUTEN_API_HITS = max(1, min(30, int(os.getenv("RAKUTEN_API_HITS", "20"))))
RAKUTEN_API_SORT = os.getenv("RAKUTEN_API_SORT", "standard").strip()
RAKUTEN_API_ENABLED = os.getenv("RAKUTEN_API_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
RAKUTEN_API_DEMO_ENABLED = os.getenv("RAKUTEN_API_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

YAHOO_AUCTION_ENABLED = os.getenv("YAHOO_AUCTION_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
YAHOO_AUCTION_DEMO_ENABLED = os.getenv("YAHOO_AUCTION_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
YAHOO_AUCTION_DATA_SOURCE = os.getenv("YAHOO_AUCTION_DATA_SOURCE", "").strip()
YAHOO_AUCTION_TIMEOUT = max(1, int(os.getenv("YAHOO_AUCTION_TIMEOUT", "10")))
YAHOO_AUCTION_MAX_RETRIES = max(0, int(os.getenv("YAHOO_AUCTION_MAX_RETRIES", "0")))
YAHOO_AUCTION_HITS = max(1, min(30, int(os.getenv("YAHOO_AUCTION_HITS", "20"))))
YAHOO_AUCTION_SORT = os.getenv("YAHOO_AUCTION_SORT", "end_time").strip()

USED_LUXURY_DEMO_ENABLED = os.getenv("USED_LUXURY_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

VESTIAIRE_ENABLED = os.getenv("VESTIAIRE_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
VESTIAIRE_DEMO_ENABLED = os.getenv("VESTIAIRE_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
VESTIAIRE_TIMEOUT_SECONDS = max(1, int(os.getenv("VESTIAIRE_TIMEOUT_SECONDS", "10")))
VESTIAIRE_PAGE_SIZE = max(1, min(50, int(os.getenv("VESTIAIRE_PAGE_SIZE", "20"))))
VESTIAIRE_MAX_PAGES = max(1, min(20, int(os.getenv("VESTIAIRE_MAX_PAGES", "1"))))
VESTIAIRE_DEFAULT_CURRENCY = os.getenv("VESTIAIRE_DEFAULT_CURRENCY", "JPY").strip().upper()
VESTIAIRE_DEMO_FIXTURE_PATH = os.getenv("VESTIAIRE_DEMO_FIXTURE_PATH", "vestiaire_search_normal.json").strip()
VESTIAIRE_ALLOW_UNKNOWN_CURRENCY = os.getenv("VESTIAIRE_ALLOW_UNKNOWN_CURRENCY", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
VESTIAIRE_INCLUDE_INACTIVE = os.getenv("VESTIAIRE_INCLUDE_INACTIVE", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
VESTIAIRE_INCLUDE_SOLD = os.getenv("VESTIAIRE_INCLUDE_SOLD", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

FASHIONPHILE_ENABLED = os.getenv("FASHIONPHILE_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_DEMO_ENABLED = os.getenv("FASHIONPHILE_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_TIMEOUT_SECONDS = max(1, int(os.getenv("FASHIONPHILE_TIMEOUT_SECONDS", "10")))
FASHIONPHILE_PAGE_SIZE = max(1, min(50, int(os.getenv("FASHIONPHILE_PAGE_SIZE", "20"))))
FASHIONPHILE_MAX_PAGES = max(1, min(20, int(os.getenv("FASHIONPHILE_MAX_PAGES", "1"))))
FASHIONPHILE_DEFAULT_CURRENCY = os.getenv("FASHIONPHILE_DEFAULT_CURRENCY", "JPY").strip().upper()
FASHIONPHILE_DEMO_FIXTURE_PATH = os.getenv(
    "FASHIONPHILE_DEMO_FIXTURE_PATH", "fashionphile_search_normal.json"
).strip()
FASHIONPHILE_ALLOW_UNKNOWN_CURRENCY = os.getenv(
    "FASHIONPHILE_ALLOW_UNKNOWN_CURRENCY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_INCLUDE_UNAVAILABLE = os.getenv(
    "FASHIONPHILE_INCLUDE_UNAVAILABLE", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_INCLUDE_SOLD = os.getenv("FASHIONPHILE_INCLUDE_SOLD", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_INCLUDE_RESERVED = os.getenv(
    "FASHIONPHILE_INCLUDE_RESERVED", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
FASHIONPHILE_INCLUDE_DISCOUNTED_ONLY = os.getenv(
    "FASHIONPHILE_INCLUDE_DISCOUNTED_ONLY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

THEREALREAL_ENABLED = os.getenv("THEREALREAL_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_DEMO_ENABLED = os.getenv("THEREALREAL_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_TIMEOUT_SECONDS = max(1, int(os.getenv("THEREALREAL_TIMEOUT_SECONDS", "10")))
THEREALREAL_PAGE_SIZE = max(1, min(50, int(os.getenv("THEREALREAL_PAGE_SIZE", "20"))))
THEREALREAL_MAX_PAGES = max(1, min(20, int(os.getenv("THEREALREAL_MAX_PAGES", "1"))))
THEREALREAL_DEFAULT_CURRENCY = os.getenv("THEREALREAL_DEFAULT_CURRENCY", "JPY").strip().upper()
THEREALREAL_DEMO_FIXTURE_PATH = os.getenv(
    "THEREALREAL_DEMO_FIXTURE_PATH", "therealreal_search_normal.json"
).strip()
THEREALREAL_ALLOW_UNKNOWN_CURRENCY = os.getenv(
    "THEREALREAL_ALLOW_UNKNOWN_CURRENCY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_INCLUDE_UNAVAILABLE = os.getenv(
    "THEREALREAL_INCLUDE_UNAVAILABLE", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_INCLUDE_SOLD = os.getenv("THEREALREAL_INCLUDE_SOLD", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_INCLUDE_RESERVED = os.getenv(
    "THEREALREAL_INCLUDE_RESERVED", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_INCLUDE_FINAL_SALE = os.getenv(
    "THEREALREAL_INCLUDE_FINAL_SALE", "true"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
THEREALREAL_INCLUDE_DISCOUNTED_ONLY = os.getenv(
    "THEREALREAL_INCLUDE_DISCOUNTED_ONLY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

GRAILED_ENABLED = os.getenv("GRAILED_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_DEMO_ENABLED = os.getenv("GRAILED_DEMO_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_TIMEOUT_SECONDS = max(1, int(os.getenv("GRAILED_TIMEOUT_SECONDS", "10")))
GRAILED_PAGE_SIZE = max(1, min(50, int(os.getenv("GRAILED_PAGE_SIZE", "20"))))
GRAILED_MAX_PAGES = max(1, min(20, int(os.getenv("GRAILED_MAX_PAGES", "1"))))
GRAILED_DEFAULT_CURRENCY = os.getenv("GRAILED_DEFAULT_CURRENCY", "JPY").strip().upper()
GRAILED_DEMO_FIXTURE_PATH = os.getenv(
    "GRAILED_DEMO_FIXTURE_PATH", "grailed_search_normal.json"
).strip()
GRAILED_ALLOW_UNKNOWN_CURRENCY = os.getenv(
    "GRAILED_ALLOW_UNKNOWN_CURRENCY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_INCLUDE_UNAVAILABLE = os.getenv(
    "GRAILED_INCLUDE_UNAVAILABLE", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_INCLUDE_SOLD = os.getenv("GRAILED_INCLUDE_SOLD", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_INCLUDE_RESERVED = os.getenv(
    "GRAILED_INCLUDE_RESERVED", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_INCLUDE_OFFER_ENABLED_ONLY = os.getenv(
    "GRAILED_INCLUDE_OFFER_ENABLED_ONLY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_INCLUDE_DISCOUNTED_ONLY = os.getenv(
    "GRAILED_INCLUDE_DISCOUNTED_ONLY", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GRAILED_REQUIRE_VERIFIED_SELLER = os.getenv(
    "GRAILED_REQUIRE_VERIFIED_SELLER", "false"
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
