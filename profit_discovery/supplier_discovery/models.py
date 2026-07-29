"""Multi supplier discovery service models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from profit_discovery.discovery_runner.models import BatchDiscoveryResult, DiscoveryCandidateResult
from supplier.base import SupplierClient


@dataclass(frozen=True, slots=True)
class SupplierDiscoverySource:
    """One registered overseas supplier source."""

    supplier_name: str
    client: SupplierClient
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SupplierDiscoveryResult:
    """Evaluation output for one supplier source."""

    source_name: str
    batch_result: BatchDiscoveryResult | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MultiSupplierDiscoveryResult:
    """Aggregated multi-supplier discovery output."""

    total_sources: int
    total_products: int
    results: tuple[SupplierDiscoveryResult, ...]
    ranked_candidates: tuple[DiscoveryCandidateResult, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
