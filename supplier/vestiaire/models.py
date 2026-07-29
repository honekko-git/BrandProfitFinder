"""Vestiaire Collective supplier-native product model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VestiaireProduct:
    """Fixture-backed Vestiaire product before supplier normalization."""

    external_id: str
    title: str
    brand: str
    category: str
    condition: str
    purchase_price: float
    currency: str
    metadata: dict[str, Any] = field(default_factory=dict)
    model_number: str | None = None
    url: str | None = None
    condition_notes: str | None = None
    availability: str = "in_stock"

    def to_dict(self) -> dict[str, Any]:
        """Serialize Vestiaire product fields."""
        return asdict(self)
