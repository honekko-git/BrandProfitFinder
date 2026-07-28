"""Tests for Farfetch main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_farfetch_demo_client,
    is_farfetch_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.farfetch_exceptions import FarfetchConfigurationError
from marketplace.farfetch_settings import FarfetchSettings
from marketplace.marketplace_factory import create_marketplace


def test_demo_cli_flag() -> None:
    assert is_farfetch_demo_requested(["--demo-farfetch"]) is True


def test_resolve_marketplace() -> None:
    assert resolve_marketplace_name(["--demo-farfetch"]) == "farfetch"


def test_demo_client_fixture() -> None:
    assert build_farfetch_demo_client() is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "ff_demo.xlsx")
    monkeypatch.setattr("main.FARFETCH_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="farfetch").exists()


def test_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "ff_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.FARFETCH_DEMO_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert run_phase3(marketplace_name="farfetch").exists()


def test_factory_config_error() -> None:
    with pytest.raises(FarfetchConfigurationError):
        create_marketplace("farfetch", farfetch_settings=FarfetchSettings.from_env())
