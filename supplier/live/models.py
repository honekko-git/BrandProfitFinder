"""Supplier live integration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SupplierLiveResponse:
    """Normalized live supplier HTTP response envelope."""

    supplier_name: str
    status_code: int
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
