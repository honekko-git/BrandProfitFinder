"""Tests for GOAT main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_goat_demo_client,
    is_goat_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.goat_exceptions import GoatConfigurationError
from marketplace.goat_marketplace import GoatMarketplace
from marketplace.goat_settings import GoatSettings
from marketplace.marketplace_factory import create_marketplace


def test_demo_cli_flag() -> None:
    assert is_goat_demo_requested(["--demo-goat"]) is True


def test_resolve_marketplace() -> None:
    assert resolve_marketplace_name(["--demo-goat"]) == "goat"


def test_demo_client_fixture() -> None:
    assert build_goat_demo_client() is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "goat_demo.xlsx")
    monkeypatch.setattr("main.GOAT_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="goat").exists()


def test_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "goat_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.GOAT_DEMO_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="goat").exists()


def test_factory_config_error() -> None:
    with pytest.raises(GoatConfigurationError):
        create_marketplace("goat", goat_settings=GoatSettings.from_env())


def test_stockx_demo_still_works(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "stockx_regression.xlsx")
    monkeypatch.setattr("main.STOCKX_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="stockx").exists()
