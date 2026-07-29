"""Overseas new supplier domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class OverseasNewProduct:
    """Overseas new product payload before supplier normalization."""

    supplier_name: str
    external_id: str
    title: str
    brand: str
    category: str
    purchase_price: float
    currency: str
    url: str
    image_urls: list[str]
    availability: str
    metadata: dict[str, Any] = field(default_factory=dict)
    model_number: str | None = None
    jan_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize overseas new product fields."""
        return asdict(self)
