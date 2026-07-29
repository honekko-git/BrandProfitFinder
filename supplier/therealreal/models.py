"""TheRealReal supplier-native product model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class TheRealRealProduct:
    """Fixture-backed TheRealReal product before supplier normalization."""

    external_id: str
    title: str
    brand: str
    category: str
    condition: str
    purchase_price: float
    currency: str
    url: str
    image_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    model_number: str | None = None
    authentication_notes: str | None = None
    condition_notes: str | None = None
    availability: str = "in_stock"

    def to_dict(self) -> dict[str, Any]:
        """Serialize TheRealReal product fields."""
        return asdict(self)
