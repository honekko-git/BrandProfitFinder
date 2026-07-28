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
