"""Tests for Fashionphile supplier-layer settings."""

from __future__ import annotations

from supplier.fashionphile.settings import FashionphileSettings as SupplierFashionphileSettings


def test_supplier_fashionphile_settings_defaults() -> None:
    settings = SupplierFashionphileSettings.default()

    assert settings.enabled is False
    assert settings.use_live is False
    assert settings.endpoint is None
    assert settings.api_key is None
    assert settings.live_enabled is False


def test_supplier_fashionphile_settings_live_enabled_flag() -> None:
    settings = SupplierFashionphileSettings(
        enabled=True,
        use_live=True,
        endpoint="https://example.invalid/fashionphile",
        api_key="secret-token",
    )

    assert settings.live_enabled is True
    assert settings.endpoint == "https://example.invalid/fashionphile"
    assert settings.api_key == "secret-token"


def test_supplier_fashionphile_settings_from_env(monkeypatch) -> None:
    monkeypatch.setenv("FASHIONPHILE_SUPPLIER_ENABLED", "true")
    monkeypatch.setenv("FASHIONPHILE_SUPPLIER_USE_LIVE", "1")
    monkeypatch.setenv("FASHIONPHILE_SUPPLIER_ENDPOINT", "https://example.invalid/fashionphile")
    monkeypatch.setenv("FASHIONPHILE_SUPPLIER_API_KEY", "test-key")

    settings = SupplierFashionphileSettings.from_env()

    assert settings.enabled is True
    assert settings.use_live is True
    assert settings.live_enabled is True
    assert settings.endpoint == "https://example.invalid/fashionphile"
    assert settings.api_key == "test-key"
