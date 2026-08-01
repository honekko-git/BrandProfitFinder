"""Browser pipeline for batch real profit discovery."""

from __future__ import annotations

from pathlib import Path

from app.storage.batch_profit_repository import BatchProfitRepository
from app.storage.yahoo_cache_repository import YahooSearchCacheRepository
from app.store import BatchProfitResultStore
from profit_discovery.discovery_validation.batch_profit.candidate_import import (
    BatchImportResult,
    candidates_from_market_listings,
    load_batch_candidates_from_csv,
)
from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitRun
from profit_discovery.discovery_validation.batch_profit.pipeline import (
    HARD_CANDIDATE_MAX,
    run_batch_profit,
)


def execute_batch_profit_search(
    *,
    store: BatchProfitResultStore,
    repository: BatchProfitRepository,
    candidates: list,
    cost_profile_name: str = "standard",
    use_cache: bool = True,
    html_by_query: dict[str, str] | None = None,
    import_errors: tuple[str, ...] = (),
    database_path: Path | str | None = None,
) -> BatchProfitRun:
    """Run batch profit discovery and persist results."""
    profile_store = CostProfileStore(
        profiles=default_cost_profiles(),
        storage_path=Path("data/cost_profiles.json"),
    )
    profile = profile_store.get(cost_profile_name)
    run = run_batch_profit(
        candidates,
        cost_profile=profile,
        use_cache=use_cache,
        cache_repository=YahooSearchCacheRepository(database_path=database_path),
        html_by_query=html_by_query,
        import_errors=import_errors,
    )
    repository.save_run(run)
    store.save(run)
    return run


def load_candidates_from_csv(path: Path | str, *, limit: int = HARD_CANDIDATE_MAX) -> BatchImportResult:
    return load_batch_candidates_from_csv(path, limit=min(limit, HARD_CANDIDATE_MAX))


def load_candidates_from_listings(listings, *, limit: int = HARD_CANDIDATE_MAX) -> BatchImportResult:
    return candidates_from_market_listings(listings, limit=min(limit, HARD_CANDIDATE_MAX))
