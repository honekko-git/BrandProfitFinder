"""Analysis versioning: outdated profit results are re-selected for analysis."""

from __future__ import annotations

import inspect
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from marketplace.acquisition_workspace.analysis_version import (
    PROFIT_ANALYSIS_VERSION,
    REANALYSIS_REASON,
    STATUS_ANALYZED,
    STATUS_NEEDS_REANALYSIS,
    analysis_status_view,
    is_profit_analysis_current,
    needs_profit_reanalysis,
)
from marketplace.acquisition_workspace.continuous_analysis import (
    ContinuousAnalysisController,
    reset_continuous_analysis_controller_for_tests,
)
from marketplace.acquisition_workspace.models import RuntimeMode
from marketplace.acquisition_workspace.profit_bridge import apply_profit_results
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.connectors.models import MarketListing
from datetime import UTC, datetime
from tests.acquisition_test_helpers import make_candidate


def _service(tmp_path: Path, name: str = "version.db") -> AcquisitionWorkspaceService:
    return AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / name)
    )


def _mark_analyzed(candidate, *, version: str):
    return replace(
        candidate,
        last_profit_batch_id="batch-old",
        last_profit_checked_at="2026-01-01T00:00:00+00:00",
        last_gross_profit=Decimal("1000"),
        last_net_profit=Decimal("800"),
        last_decision="HOLD",
        discovery_metadata=replace(
            candidate.discovery_metadata,
            runtime_mode=RuntimeMode.FIXTURE.value,
            profit_analysis_version=version,
        ),
    )


def _fake_profit_run(candidates, **kwargs):
    from profit_discovery.discovery_validation.batch_profit.models import (
        BatchProfitRun,
        BatchRunSummary,
    )

    results = tuple(
        SimpleNamespace(
            candidate=candidate,
            retrieved_at="2026-08-01T12:00:00+00:00",
            batch_decision="HOLD",
            gross_estimated_profit=Decimal("2000"),
            net_estimated_profit=Decimal("1500"),
            warnings=(),
            comparable_warning="",
            yahoo_data_source="FIXTURE",
            yahoo_queries=(),
            raw_sample_count=0,
            accepted_comparable_count=0,
            estimated_costs=SimpleNamespace(net_profit_complete=True),
            rank=index + 1,
        )
        for index, candidate in enumerate(candidates)
    )
    return BatchProfitRun(
        summary=BatchRunSummary(
            batch_id=f"batch-ver-{uuid4().hex[:8]}",
            started_at="2026-08-01T12:00:00+00:00",
            completed_at="2026-08-01T12:00:01+00:00",
            total_candidates=len(candidates),
            processed_count=len(candidates),
            strong_candidate_count=0,
            review_count=len(candidates),
            hold_count=0,
            reject_count=0,
            failed_count=0,
            blocked_count=0,
            total_yahoo_requests=0,
            cache_hits=0,
            exchange_rate="160",
            cost_profile="standard",
            status="ok",
        ),
        results=results,
    )


def test_old_version_is_selected_again(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, "old.db")
    batch = service.import_existing_listings(
        [
            MarketListing(
                id="fp-old-1",
                title="Chanel Classic Flap Bag Black Caviar",
                brand="Chanel",
                category="Bag",
                condition="Excellent",
                price=Decimal("2500"),
                currency="USD",
                market_name="Fashionphile",
                url="https://www.fashionphile.com/products/old-1",
                source_type="EXISTING_IMPORT",
                created_at=datetime.now(tz=UTC),
            )
        ],
        name="OldVer",
    )
    _, rows = service.get_batch(batch.workspace_batch_id)
    stale = _mark_analyzed(rows[0], version="v1")
    service._repo.update_candidate(stale)

    assert needs_profit_reanalysis(stale)
    assert not is_profit_analysis_current(stale)
    status = analysis_status_view(stale)
    assert status.label == STATUS_NEEDS_REANALYSIS
    assert status.reason == REANALYSIS_REASON

    seen: list[str] = []

    def _tracking_run(candidates, **kwargs):
        seen.extend(item.candidate_id for item in candidates)
        return _fake_profit_run(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _tracking_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    assert getattr(run.summary, "status", "") != "already_complete"
    assert stale.candidate_id in seen

    _, after = service.get_batch(batch.workspace_batch_id)
    assert is_profit_analysis_current(after[0])
    assert after[0].discovery_metadata.profit_analysis_version == PROFIT_ANALYSIS_VERSION


def test_current_version_is_skipped(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, "cur.db")
    batch = service.import_existing_listings(
        [
            MarketListing(
                id="fp-cur-1",
                title="Louis Vuitton Neverfull MM Monogram",
                brand="Louis Vuitton",
                category="Bag",
                condition="Excellent",
                price=Decimal("1800"),
                currency="USD",
                market_name="Fashionphile",
                url="https://www.fashionphile.com/products/cur-1",
                source_type="EXISTING_IMPORT",
                created_at=datetime.now(tz=UTC),
            )
        ],
        name="CurVer",
    )
    _, rows = service.get_batch(batch.workspace_batch_id)
    current = _mark_analyzed(rows[0], version=PROFIT_ANALYSIS_VERSION)
    service._repo.update_candidate(current)

    assert is_profit_analysis_current(current)
    assert analysis_status_view(current).label == STATUS_ANALYZED

    called = {"n": 0}

    def _tracking_run(candidates, **kwargs):
        called["n"] += 1
        return _fake_profit_run(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _tracking_run,
    )

    run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    assert run.summary.status == "already_complete"
    assert called["n"] == 0


def test_continuous_analysis_handles_outdated_candidates(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    service = _service(tmp_path, "cont-ver.db")
    listings = [
        MarketListing(
            id=f"fp-cont-ver-{index}",
            title=f"Gucci Dionysus Wallet Product {index} SKU{index}",
            brand="Gucci",
            category="Wallet",
            condition="Excellent",
            price=Decimal(str(400 + index)),
            currency="USD",
            market_name="Fashionphile",
            url=f"https://www.fashionphile.com/products/cont-ver-{index}",
            source_type="EXISTING_IMPORT",
            created_at=datetime.now(tz=UTC),
        )
        for index in range(3)
    ]
    batch = service.import_existing_listings(listings, name="ContVer")
    _, rows = service.get_batch(batch.workspace_batch_id)
    for item in rows:
        service._repo.update_candidate(_mark_analyzed(item, version="v1"))

    progress_before = ContinuousAnalysisController._workspace_stats(
        service, batch.workspace_batch_id
    )
    assert progress_before["analyzed"] == 0
    assert progress_before["remaining"] == 3

    seen: list[set[str]] = []

    def _tracking_run(candidates, **kwargs):
        seen.append({item.candidate_id for item in candidates})
        return _fake_profit_run(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _tracking_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    controller = ContinuousAnalysisController()
    controller.start(batch.workspace_batch_id, service, use_cache=False)

    import time

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if controller.get_progress(batch.workspace_batch_id, service).status == "complete":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("continuous analysis did not complete")

    final = controller.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 3
    assert final.remaining == 0
    assert len(seen) == 1
    assert len(seen[0]) == 3

    _, after = service.get_batch(batch.workspace_batch_id)
    assert all(is_profit_analysis_current(item) for item in after)


def test_apply_profit_results_stores_current_version() -> None:
    candidate = make_candidate(selected=True)
    updated = apply_profit_results(
        [candidate],
        batch_id="bp-ver",
        results_by_candidate_id={
            candidate.candidate_id: {
                "retrieved_at": "2026-08-01T00:00:00+00:00",
                "batch_decision": "HOLD",
                "gross_estimated_profit": Decimal("1"),
                "net_estimated_profit": Decimal("1"),
                "warning": "",
                "yahoo_data_source": "FIXTURE",
                "yahoo_queries": (),
                "candidate_count": 1,
                "comparable_count": 1,
                "estimated_from_multiple_results": False,
                "median_used": True,
                "net_profit_complete": True,
            }
        },
    )
    assert updated[0].discovery_metadata.profit_analysis_version == PROFIT_ANALYSIS_VERSION
    assert is_profit_analysis_current(updated[0])


def test_missing_version_treated_as_outdated() -> None:
    candidate = _mark_analyzed(make_candidate(), version="")
    assert needs_profit_reanalysis(candidate)
    assert analysis_status_view(candidate).reason == REANALYSIS_REASON


def test_profit_calculator_unchanged() -> None:
    from price_compare import profit_calculator

    source = inspect.getsource(profit_calculator)
    assert "PROFIT_ANALYSIS_VERSION" not in source
    assert "analysis_version" not in source
    assert "profit_analysis_version" not in source


def test_ranking_formula_unchanged() -> None:
    from marketplace.acquisition_workspace import ranking

    source = inspect.getsource(ranking)
    assert "PROFIT_ANALYSIS_VERSION" not in source
    assert "analysis_version" not in source
    # Ranking still uses the same overall composition helpers.
    assert "overall_score" in source
    assert "profit_score" in source
    assert "roi_score" in source
