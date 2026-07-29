"""Tests for supplier live models."""

from __future__ import annotations

from supplier.live.models import SupplierLiveResponse


def test_supplier_live_response_creation() -> None:
    response = SupplierLiveResponse(
        supplier_name="fashionphile",
        status_code=200,
        payload={"items": [{"external_id": "fp-001"}]},
        metadata={"endpoint": "/search"},
    )

    assert response.supplier_name == "fashionphile"
    assert response.status_code == 200
    assert response.payload["items"][0]["external_id"] == "fp-001"
    assert response.metadata["endpoint"] == "/search"


def test_supplier_live_response_defaults_metadata() -> None:
    response = SupplierLiveResponse(
        supplier_name="therealreal",
        status_code=404,
        payload={"items": []},
    )

    assert response.metadata == {}
