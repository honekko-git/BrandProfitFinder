"""Tests for Fashionphile main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_fashionphile_demo_client,
    is_fashionphile_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.fashionphile_exceptions import FashionphileConfigurationError
from marketplace.fashionphile_settings import FashionphileSettings
from marketplace.marketplace_factory import create_marketplace


def test_demo_cli_flag() -> None:
    assert is_fashionphile_demo_requested(["--demo-fashionphile"]) is True


def test_resolve_marketplace_fashionphile() -> None:
    assert resolve_marketplace_name(["--demo-fashionphile"]) == "fashionphile"


def test_demo_client_fixture() -> None:
    client = build_fashionphile_demo_client()
    assert client is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "fashionphile_demo.xlsx")
    monkeypatch.setattr("main.FASHIONPHILE_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3(marketplace_name="fashionphile")

    assert output_path.exists()


def test_fashionphile_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "fashionphile_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.FASHIONPHILE_DEMO_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3(marketplace_name="fashionphile")

    assert output_path.exists()


def test_factory_config_error_without_client() -> None:
    with pytest.raises(FashionphileConfigurationError):
        create_marketplace("fashionphile", fashionphile_settings=FashionphileSettings.from_env())


def test_default_run_no_fashionphile_fixture(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "local.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.FASHIONPHILE_DEMO_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3()

    assert output_path.exists()
    assert resolve_marketplace_name([]) == "local"
