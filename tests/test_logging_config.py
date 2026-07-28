"""Foundation tests for config.logging_config."""

import logging

from config.logging_config import setup_logging


def test_setup_logging_returns_logger() -> None:
    logger = setup_logging("brand_profit_finder.test")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "brand_profit_finder.test"


def test_setup_logging_is_idempotent() -> None:
    first_count = len(logging.getLogger().handlers)
    setup_logging()
    second_count = len(logging.getLogger().handlers)
    assert second_count == first_count


def test_logger_emits_message(caplog) -> None:
    caplog.set_level(logging.INFO)
    logger = setup_logging("foundation.logging")
    logger.info("foundation logging works")
    assert any("foundation logging works" in record.message for record in caplog.records)
