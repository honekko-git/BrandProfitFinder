"""Supplier to domestic market connector models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from marketplace.yahoo_auction.models import DomesticMarketPrice


@dataclass(frozen=True, slots=True)
class MarketSearchRequest:
    """Normalized domestic market search request derived from a supplier product."""

    supplier_name: str
    product_name: str
    brand: str
    model_number: str | None
    keywords: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MarketEvaluationResult:
    """Bridge result linking one supplier product to domestic market intelligence."""

    supplier_product_id: str
    domestic_market_price: DomesticMarketPrice | None
    matched_keyword: str
    confidence_score: float
    metadata: dict[str, Any] = field(default_factory=dict)
