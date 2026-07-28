"""
Logging configuration for BrandProfitFinder.

Centralizes log format, handlers, and setup.
"""

import logging
from logging.handlers import RotatingFileHandler

from config.settings import LOG_DIR, LOG_FILE, LOG_LEVEL

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

_CONFIGURED = False


def setup_logging(name: str | None = None) -> logging.Logger:
    """
    Configure application logging with console and rotating file handlers.

    Args:
        name: Optional logger name. Uses root logger when None.

    Returns:
        Configured logger instance.
    """
    global _CONFIGURED

    root = logging.getLogger()
    if not _CONFIGURED:
        level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
        root.setLevel(level)

        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        _CONFIGURED = True

    return logging.getLogger(name) if name else root
