"""Batch discovery runner models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from models.price_result import PriceResult
from profit_discovery.market_connector.models import MarketEvaluationResult
from profit_discovery.models import BuyDecisionResult
from profit_intelligence.discovery_models import DiscoveryScore
from supplier.models import SupplierProduct


class DiscoveryCandidateStatus(StrEnum):
    """Evaluation status for one supplier product in a batch run."""

    SUCCESS = "SUCCESS"
    NO_MARKET_DATA = "NO_MARKET_DATA"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DiscoveryCandidateResult:
    """One evaluated supplier product result."""

    supplier_product: SupplierProduct
    status: DiscoveryCandidateStatus
    market_evaluation: MarketEvaluationResult | None = None
    profit_result: PriceResult | None = None
    discovery_score: DiscoveryScore | None = None
    buy_decision: BuyDecisionResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BatchDiscoveryResult:
    """Batch execution output for supplier discovery evaluation."""

    total_products: int
    evaluated_products: int
    buy_candidates: int
    results: tuple[DiscoveryCandidateResult, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
