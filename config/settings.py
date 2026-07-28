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
