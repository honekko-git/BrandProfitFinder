"""Storage interfaces and implementations for dashboard search snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from marketplace.connectors.models import MarketListing
from marketplace.connectors.execution import MarketConnectorExecutionResult
from profit_discovery.arbitrage.models import ArbitrageOpportunity
from profit_discovery.discovery_runner.models import DiscoveryCandidateResult
from profit_discovery.discovery_validation.models import ValidationOpportunity
from profit_discovery.profit_ranking.models import UsedLuxuryProfitRankedResult


@dataclass
class DashboardSearchSnapshot:
    """Latest dashboard search output kept for detail-page lookup."""

    brand: str
    category: str
    market_mode: str
    arbitrage_ranking: list[ArbitrageOpportunity] = field(default_factory=list)
    profit_ranking: list[UsedLuxuryProfitRankedResult] = field(default_factory=list)
    candidates_by_id: dict[str, DiscoveryCandidateResult] = field(default_factory=dict)
    listings_by_id: dict[str, MarketListing] = field(default_factory=dict)
    connector_executions: dict[str, MarketConnectorExecutionResult] = field(default_factory=dict)


@dataclass
class ValidationSearchSnapshot:
    """Latest profit validation search output."""

    brand: str
    category: str
    market_mode: str
    validation_ranking: list[ValidationOpportunity] = field(default_factory=list)
    candidates_by_id: dict[str, DiscoveryCandidateResult] = field(default_factory=dict)
    real_profit_results: list = field(default_factory=list)
    controlled_live_results: list = field(default_factory=list)
    verification_mode: str = "STANDARD"
    blocking_reason: str = ""


class ValidationResultStore:
    """In-memory store for profit validation search snapshots."""

    def __init__(self) -> None:
        self._snapshot: ValidationSearchSnapshot | None = None

    def save(self, snapshot: ValidationSearchSnapshot) -> None:
        self._snapshot = snapshot

    def get(self) -> ValidationSearchSnapshot | None:
        return self._snapshot

    def clear(self) -> None:
        self._snapshot = None

    def get_validation(self, product_id: str) -> ValidationOpportunity | None:
        if self._snapshot is None:
            return None
        for item in self._snapshot.validation_ranking:
            if item.external_id == product_id:
                return item
        return None

    def get_candidate(self, product_id: str) -> DiscoveryCandidateResult | None:
        if self._snapshot is None:
            return None
        return self._snapshot.candidates_by_id.get(product_id)


class DashboardSnapshotStore(Protocol):
    """Interface for dashboard snapshot persistence backends."""

    def save(self, snapshot: DashboardSearchSnapshot) -> None:
        """Persist one dashboard search snapshot."""

    def get(self) -> DashboardSearchSnapshot | None:
        """Return the latest dashboard search snapshot."""

    def clear(self) -> None:
        """Remove the latest dashboard search snapshot."""


class InMemoryDashboardSnapshotStore:
    """In-memory dashboard snapshot store for MVP browser sessions."""

    def __init__(self) -> None:
        self._snapshot: DashboardSearchSnapshot | None = None

    def save(self, snapshot: DashboardSearchSnapshot) -> None:
        self._snapshot = snapshot

    def get(self) -> DashboardSearchSnapshot | None:
        return self._snapshot

    def clear(self) -> None:
        self._snapshot = None


class DashboardResultStore(InMemoryDashboardSnapshotStore):
    """Backward-compatible alias for the in-memory dashboard store."""

    def get_arbitrage(self, product_id: str) -> ArbitrageOpportunity | None:
        if self._snapshot is None:
            return None
        for item in self._snapshot.arbitrage_ranking:
            if item.external_id == product_id:
                return item
        return None

    def get_candidate(self, product_id: str) -> DiscoveryCandidateResult | None:
        if self._snapshot is None:
            return None
        return self._snapshot.candidates_by_id.get(product_id)

    def get_profit_rank(self, product_id: str) -> UsedLuxuryProfitRankedResult | None:
        if self._snapshot is None:
            return None
        for item in self._snapshot.profit_ranking:
            if item.candidate.supplier_product.external_id == product_id:
                return item
        return None

    def get_listing(self, product_id: str) -> MarketListing | None:
        if self._snapshot is None:
            return None
        return self._snapshot.listings_by_id.get(product_id)


class SQLiteOpportunityStore:
    """SQLite-backed store for saved dashboard opportunities."""

    def __init__(
        self,
        *,
        database_path: Path | str | None = None,
        repository: object | None = None,
    ) -> None:
        from app.storage.repository import OpportunityRepository

        self._repository = repository or OpportunityRepository(database_path)

    @property
    def repository(self):
        return self._repository

    def save(self, record) -> object:
        return self._repository.save(record)

    def save_arbitrage(self, item: ArbitrageOpportunity):
        from app.storage.converters import opportunity_record_from_arbitrage

        return self._repository.save(opportunity_record_from_arbitrage(item))

    def get_by_id(self, record_id: int):
        return self._repository.get_by_id(record_id)

    def list_all(self) -> list:
        return self._repository.list_all()

    def update_status(self, record_id: int, status):
        return self._repository.update_status(record_id, status)

    def delete(self, record_id: int) -> bool:
        return self._repository.delete(record_id)

    def find_by_purchase_url(self, purchase_url: str):
        return self._repository.find_by_purchase_url(purchase_url)


class SQLiteMarketListingStore:
    """SQLite-backed store for imported market listings."""

    def __init__(
        self,
        *,
        database_path: Path | str | None = None,
        repository: object | None = None,
    ) -> None:
        from app.storage.market_listing_repository import MarketListingRepository

        self._repository = repository or MarketListingRepository(database_path)

    @property
    def repository(self):
        return self._repository

    def save_listing(self, listing: MarketListing):
        from app.storage.market_listing_converters import market_listing_record_from_listing

        return self._repository.save(market_listing_record_from_listing(listing))

    def list_all(self) -> list:
        return self._repository.list_all()

    def search(self, query: str) -> list:
        return self._repository.search(query)

    def delete(self, record_id: int) -> bool:
        return self._repository.delete(record_id)


class BatchProfitResultStore:
    """In-memory store for the latest batch profit run."""

    def __init__(self) -> None:
        self._latest = None

    def save(self, run) -> None:
        self._latest = run

    def get(self):
        return self._latest

    def clear(self) -> None:
        self._latest = None

