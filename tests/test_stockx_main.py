"""Tests for StockX main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_stockx_demo_client,
    is_stockx_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.marketplace_factory import create_marketplace
from marketplace.stockx_exceptions import StockXConfigurationError
from marketplace.stockx_settings import StockXSettings


def test_demo_cli_flag() -> None:
    assert is_stockx_demo_requested(["--demo-stockx"]) is True


def test_resolve_marketplace() -> None:
    assert resolve_marketplace_name(["--demo-stockx"]) == "stockx"


def test_demo_client_fixture() -> None:
    assert build_stockx_demo_client() is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "sx_demo.xlsx")
    monkeypatch.setattr("main.STOCKX_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="stockx").exists()


def test_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "sx_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.STOCKX_DEMO_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="stockx").exists()


def test_factory_config_error() -> None:
    with pytest.raises(StockXConfigurationError):
        create_marketplace("stockx", stockx_settings=StockXSettings.from_env())
