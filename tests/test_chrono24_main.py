"""Tests for Chrono24 main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_chrono24_demo_client,
    is_chrono24_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.chrono24_exceptions import Chrono24ConfigurationError
from marketplace.chrono24_settings import Chrono24Settings
from marketplace.marketplace_factory import create_marketplace


def test_demo_cli_flag() -> None:
    assert is_chrono24_demo_requested(["--demo-chrono24"]) is True


def test_resolve_marketplace() -> None:
    assert resolve_marketplace_name(["--demo-chrono24"]) == "chrono24"


def test_demo_client_fixture() -> None:
    assert build_chrono24_demo_client() is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "c24_demo.xlsx")
    monkeypatch.setattr("main.CHRONO24_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="chrono24").exists()


def test_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "c24_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.CHRONO24_DEMO_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="chrono24").exists()


def test_factory_config_error() -> None:
    with pytest.raises(Chrono24ConfigurationError):
        create_marketplace("chrono24", chrono24_settings=Chrono24Settings.from_env())
