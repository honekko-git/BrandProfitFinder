"""Tests for The RealReal main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_therealreal_demo_client,
    is_therealreal_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.marketplace_factory import create_marketplace
from marketplace.therealreal_exceptions import TheRealRealConfigurationError
from marketplace.therealreal_settings import TheRealRealSettings


def test_demo_cli_flag() -> None:
    assert is_therealreal_demo_requested(["--demo-therealreal"]) is True


def test_resolve_marketplace() -> None:
    assert resolve_marketplace_name(["--demo-therealreal"]) == "therealreal"


def test_demo_client_fixture() -> None:
    assert build_therealreal_demo_client() is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "trr_demo.xlsx")
    monkeypatch.setattr("main.THEREALREAL_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="therealreal").exists()


def test_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "trr_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.THEREALREAL_DEMO_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="therealreal").exists()


def test_factory_config_error() -> None:
    with pytest.raises(TheRealRealConfigurationError):
        create_marketplace("therealreal", therealreal_settings=TheRealRealSettings.from_env())
