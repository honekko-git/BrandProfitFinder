"""
Logger utility wrapper.

Provides module-level logger access without duplicating setup logic.
"""

import logging

from config.logging_config import setup_logging


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        Configured logger instance.
    """
    setup_logging()
    return logging.getLogger(name)
