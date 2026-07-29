"""Fashionphile supplier-native product model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class FashionphileProduct:
    """Fixture-backed Fashionphile product before supplier normalization."""

    external_id: str
    title: str
    brand: str
    category: str
    condition: str
    price: float
    currency: str
    url: str
    image_urls: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    model_number: str | None = None
    condition_notes: str | None = None
    authentication: dict[str, Any] | None = None
    availability: str = "in_stock"

    def to_dict(self) -> dict[str, Any]:
        """Serialize Fashionphile product fields."""
        return asdict(self)
