"""Deterministic tests for continuous sequential profit analysis."""

from __future__ import annotations

import threading
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.continuous_analysis import (
    ContinuousAnalysisController,
    get_continuous_analysis_controller,
    reset_continuous_analysis_controller_for_tests,
)
from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from marketplace.connectors.models import MarketListing
from datetime import UTC, datetime


def _listings(count: int):
    now = datetime.now(tz=UTC)
    brands = [
        "Chanel",
        "Louis Vuitton",
        "Hermes",
        "Gucci",
        "Prada",
        "Dior",
        "Celine",
        "Bottega",
        "Fendi",
        "Balenciaga",
        "Givenchy",
        "Loewe",
        "YSL",
        "Burberry",
        "Valentino",
        "Tod",
        "Coach",
        "Michael",
        "Kate",
        "Tory",
        "Samurai",
        "Iron",
        "Studio",
        "Flat",
    ]
    return [
        MarketListing(
            id=f"fp-cont-{index}",
            title=f"{brands[index % len(brands)]} Product Model Series {index} Item SKU{index}",
            brand=brands[index % len(brands)],
            category="Wallet",
            condition="Excellent",
            price=Decimal(str(200 + index * 10)),
            currency="USD",
            market_name="Fashionphile",
            url=f"https://www.fashionphile.com/products/cont-item-{index}-sku{index}",
            source_type="EXISTING_IMPORT",
            created_at=now,
        )
        for index in range(count)
    ]


def _fake_profit_run(candidates, **kwargs):
    from profit_discovery.discovery_validation.batch_profit.models import (
        BatchProfitRun,
        BatchRunSummary,
    )

    results = tuple(
        SimpleNamespace(
            candidate=candidate,
            retrieved_at=f"2026-08-01T00:00:{index:02d}+00:00",
            batch_decision="HOLD",
            gross_estimated_profit=Decimal("1000"),
            net_estimated_profit=Decimal("800"),
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
            batch_id=f"batch-cont-{uuid4().hex[:8]}",
            started_at="2026-08-01T00:00:00+00:00",
            completed_at="2026-08-01T00:00:01+00:00",
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


def _wait_until(predicate, *, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


def _service(tmp_path: Path, name: str) -> AcquisitionWorkspaceService:
    return AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / name)
    )


def _patch_pipeline(monkeypatch) -> list[set[str]]:
    seen: list[set[str]] = []

    def _tracking_run(candidates, **kwargs):
        ids = {item.candidate_id for item in candidates}
        for prior in seen:
            assert ids.isdisjoint(prior)
        seen.append(ids)
        return _fake_profit_run(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _tracking_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )
    return seen


def test_twenty_candidates_one_batch_complete(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    seen = _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "c20.db")
    batch = service.import_existing_listings(_listings(20), name="C20")
    controller = ContinuousAnalysisController()
    progress = controller.start(batch.workspace_batch_id, service, use_cache=False)
    _wait_until(lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete")
    final = controller.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 20
    assert final.remaining == 0
    assert final.user_message == "すべて分析済みです。"
    assert len(seen) == 1
    assert len(seen[0]) == MAX_BATCH_CANDIDATES


def test_seventy_five_advances_20_40_60_75(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    seen = _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "c75.db")
    batch = service.import_existing_listings(_listings(75), name="C75")
    milestones: list[int] = []
    lock = threading.Lock()

    real_run = service.run_batch_profit

    def _wrapped(workspace_batch_id, **kwargs):
        run = real_run(workspace_batch_id, **kwargs)
        _, rows = service.get_batch(workspace_batch_id)
        analyzed = sum(1 for item in rows if item.last_profit_checked_at)
        with lock:
            milestones.append(analyzed)
        return run

    controller = ContinuousAnalysisController()
    controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    _wait_until(lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete")
    assert milestones == [20, 40, 60, 75]
    assert len(seen) == 4
    final = controller.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 75
    assert final.remaining == 0


def test_two_hundred_six_auto_completes_without_repeats(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    seen = _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "c206.db")
    batch = service.import_existing_listings(_listings(206), name="C206")
    controller = ContinuousAnalysisController()
    controller.start(batch.workspace_batch_id, service, use_cache=False)
    _wait_until(
        lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete",
        timeout=60.0,
    )
    final = controller.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 206
    assert final.remaining == 0
    assert len(seen) == 11  # 10*20 + 6
    all_ids = [cid for group in seen for cid in group]
    assert len(all_ids) == len(set(all_ids)) == 206


def test_stop_after_second_batch_then_resume(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "cstop.db")
    batch = service.import_existing_listings(_listings(80), name="CStop")
    controller = ContinuousAnalysisController()
    calls = {"n": 0}
    real_run = service.run_batch_profit

    def _wrapped(workspace_batch_id, **kwargs):
        calls["n"] += 1
        run = real_run(workspace_batch_id, **kwargs)
        if calls["n"] == 2:
            controller.stop(workspace_batch_id, service)
        return run

    controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    _wait_until(
        lambda: controller.get_progress(batch.workspace_batch_id, service).status == "stopped",
        timeout=30.0,
    )
    mid = controller.get_progress(batch.workspace_batch_id, service)
    assert mid.analyzed == 40
    assert mid.remaining == 40

    # Ensure prior worker thread has fully exited before resume.
    prior = controller._sessions.get(batch.workspace_batch_id)
    if prior and prior.thread:
        prior.thread.join(timeout=5.0)

    resumed = controller.start(batch.workspace_batch_id, service, use_cache=False)
    assert resumed.status in {"running", "complete"}
    _wait_until(
        lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete",
        timeout=30.0,
    )
    final = controller.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 80
    assert final.remaining == 0


def test_already_complete_immediate_message(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "cdone.db")
    batch = service.import_existing_listings(_listings(20), name="CDone")
    service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    controller = ContinuousAnalysisController()
    progress = controller.start(batch.workspace_batch_id, service, use_cache=False)
    assert progress.status == "complete"
    assert progress.user_message == "すべて分析済みです。"
    assert progress.remaining == 0


def test_error_on_third_batch_resume_from_remaining(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "cerr.db")
    batch = service.import_existing_listings(_listings(80), name="CErr")
    controller = ContinuousAnalysisController()
    calls = {"n": 0}
    real_run = service.run_batch_profit

    def _wrapped(workspace_batch_id, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated batch failure")
        return real_run(workspace_batch_id, **kwargs)

    controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    _wait_until(lambda: controller.get_progress(batch.workspace_batch_id, service).status == "error")
    errored = controller.get_progress(batch.workspace_batch_id, service)
    assert errored.analyzed == 40
    assert errored.remaining == 40
    assert "エラー" in errored.user_message
    assert errored.last_completed_count == 40

    # Resume from remaining only.
    controller2 = ContinuousAnalysisController()
    controller2.start(batch.workspace_batch_id, service, use_cache=False)
    _wait_until(lambda: controller2.get_progress(batch.workspace_batch_id, service).status == "complete")
    final = controller2.get_progress(batch.workspace_batch_id, service)
    assert final.analyzed == 80


def test_double_start_returns_busy(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "cbusy.db")
    batch = service.import_existing_listings(_listings(60), name="CBusy")
    controller = ContinuousAnalysisController()
    gate = threading.Event()
    real_run = service.run_batch_profit

    def _wrapped(workspace_batch_id, **kwargs):
        gate.wait(timeout=5)
        return real_run(workspace_batch_id, **kwargs)

    first = controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    assert first.status in {"running", "busy"}
    second = controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    assert second.status == "busy"
    assert "実行中" in second.user_message
    gate.set()
    _wait_until(lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete")


def test_http_endpoints_and_manual_profit_unchanged(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    app = create_app(database_path=tmp_path / "chttp.db")
    # Ensure app uses same controller reset.
    reset_continuous_analysis_controller_for_tests()
    client = TestClient(app)
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "chttp.db")
    )
    batch = service.import_existing_listings(_listings(25), name="CHTTP")

    page = client.get(f"/acquisition-workspace?batch_id={batch.workspace_batch_id}")
    assert page.status_code == 200
    assert "連続分析" in page.text
    assert "利益分析" in page.text
    assert 'data-profit-continuous' in page.text

    # Manual single tranche still works.
    manual = client.post(
        f"/acquisition-workspace/{batch.workspace_batch_id}/run-profit",
        data={"cost_profile": "standard", "use_cache": "on"},
        follow_redirects=False,
    )
    assert manual.status_code == 303
    assert "Internal Server Error" not in (manual.text or "")

    _, rows = service.get_batch(batch.workspace_batch_id)
    analyzed = sum(1 for item in rows if item.last_profit_checked_at)
    assert analyzed == MAX_BATCH_CANDIDATES

    start = client.post(
        f"/acquisition-workspace/{batch.workspace_batch_id}/continuous-profit/start",
        json={"cost_profile": "standard", "use_cache": True},
    )
    assert start.status_code == 200
    body = start.json()
    assert body["status"] in {"running", "complete"}

    def _done() -> bool:
        status = client.get(
            f"/acquisition-workspace/{batch.workspace_batch_id}/continuous-profit/status"
        ).json()
        return status["status"] == "complete"

    _wait_until(_done)
    status = client.get(
        f"/acquisition-workspace/{batch.workspace_batch_id}/continuous-profit/status"
    ).json()
    assert status["analyzed"] == 25
    assert status["remaining"] == 0

    # Ranking still present after continuous completion.
    page2 = client.get(f"/acquisition-workspace?batch_id={batch.workspace_batch_id}")
    assert page2.status_code == 200
    assert "Internal Server Error" not in page2.text


def test_multi_tab_concurrency_guard_via_singleton(tmp_path: Path, monkeypatch) -> None:
    reset_continuous_analysis_controller_for_tests()
    _patch_pipeline(monkeypatch)
    service = _service(tmp_path, "ctab.db")
    batch = service.import_existing_listings(_listings(40), name="CTab")
    controller = get_continuous_analysis_controller()
    gate = threading.Event()
    real_run = service.run_batch_profit

    def _wrapped(workspace_batch_id, **kwargs):
        gate.wait(timeout=5)
        return real_run(workspace_batch_id, **kwargs)

    controller.start(batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped)
    other = get_continuous_analysis_controller().start(
        batch.workspace_batch_id, service, use_cache=False, run_batch=_wrapped
    )
    assert other.status == "busy"
    gate.set()
    _wait_until(lambda: controller.get_progress(batch.workspace_batch_id, service).status == "complete")
