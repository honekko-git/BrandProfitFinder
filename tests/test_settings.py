"""Foundation tests for config.settings."""

from pathlib import Path

from config import settings


def test_base_dir_exists() -> None:
    assert settings.BASE_DIR.is_dir()


def test_output_and_log_dirs_are_configured() -> None:
    assert settings.OUTPUT_DIR.name == "output"
    assert settings.LOG_DIR.name == "logs"
    assert isinstance(settings.OUTPUT_DIR, Path)


def test_network_defaults_are_positive() -> None:
    assert settings.REQUEST_TIMEOUT > 0
    assert settings.MAX_RETRY >= 1
    assert settings.USER_AGENT


def test_excel_and_exchange_defaults() -> None:
    assert settings.EXCEL_FILENAME.endswith(".xlsx")
    assert settings.DEFAULT_EXCHANGE_RATE > 0
