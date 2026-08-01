"""Tests for acquisition workspace to batch profit bridge."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
from marketplace.acquisition_workspace.profit_bridge import apply_profit_results, to_batch_profit_candidates
from marketplace.acquisition_workspace.workspace_service import AcquisitionWorkspaceService
from tests.acquisition_test_helpers import make_candidate

FIXTURES = Path(__file__).resolve().parent / "fixtures"
YAHOO_HTML = (FIXTURES / "browser_acquisition" / "yahoo_live_ja.html").read_text(encoding="utf-8")
from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit as _real_run_batch_profit


def test_selected_eligible_only() -> None:
    selected = make_candidate(selected=True, eligible=True)
    skipped = make_candidate(selected=False, eligible=True)
    rejected = make_candidate(selected=True, eligible=False, quality_grade="REJECTED")
    batch = to_batch_profit_candidates([selected, skipped, rejected])
    assert len(batch) == 1
    assert batch[0].candidate_id == selected.candidate_id


def test_duplicates_excluded() -> None:
    primary = make_candidate(selected=True)
    duplicate = replace(make_candidate(selected=True), duplicate_of=primary.candidate_id, candidate_id="ac-dup")
    batch = to_batch_profit_candidates([primary, duplicate])
    assert len(batch) == 1


def test_bag_category_eligible_still_requires_selection() -> None:
    bag = make_candidate(
        title="Chanel Classic Double Flap Bag",
        category="Bag",
        eligible=True,
        selected=False,
    )
    assert to_batch_profit_candidates([bag]) == []
    selected = replace(bag, selected_for_profit_check=True)
    assert len(to_batch_profit_candidates([selected])) == 1


def test_ineligible_bag_excluded_from_bridge() -> None:
    bag = make_candidate(
        title="Chanel Classic Double Flap Bag",
        category="Bag",
        eligible=False,
        selected=True,
    )
    assert to_batch_profit_candidates([bag]) == []


def test_maximum_20_raises() -> None:
    candidates = [replace(make_candidate(selected=True), candidate_id=f"ac-{index}") for index in range(21)]
    with pytest.raises(ValueError, match="Maximum 20"):
        to_batch_profit_candidates(candidates)


def _fake_profit_run(candidates, **kwargs):
    """Offline stub that marks each passed candidate as analyzed."""
    from types import SimpleNamespace
    from uuid import uuid4

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
            batch_id=f"batch-seq-{uuid4().hex[:8]}",
            started_at="2026-08-01T00:00:00+00:00",
            completed_at="2026-08-01T00:00:01+00:00",
            total_candidates=len(candidates),
            processed_count=len(candidates),
            strong_candidate_count=0,
            review_count=0,
            hold_count=len(candidates),
            reject_count=0,
            failed_count=0,
            blocked_count=0,
            total_yahoo_requests=0,
            cache_hits=0,
            exchange_rate="150",
            cost_profile="standard",
            status="completed",
        ),
        results=results,
    )


def _distinct_wallet_listings(count: int):
    from datetime import UTC, datetime

    from marketplace.connectors.models import MarketListing

    now = datetime(2026, 8, 1, tzinfo=UTC)
    brands = [
        "Chanel",
        "Louis Vuitton",
        "Hermes",
        "Gucci",
        "Prada",
        "Dior",
        "Balenciaga",
        "Fendi",
        "Bottega",
        "Celine",
        "YSL",
        "Givenchy",
        "Loewe",
        "Burberry",
        "Coach",
        "MCM",
        "Tory",
        "Chloe",
        "Mulberry",
        "Valentino",
        "Versace",
        "Jimmy",
        "Roger",
        "Alaia",
        "Cartier",
        "Tiffany",
        "Bulgari",
        "Rolex",
        "Omega",
        "Tag",
        "Montblanc",
        "Dunhill",
        "Ferragamo",
        "Tod",
        "Kenzo",
        "Moschino",
        "Furla",
        "Longchamp",
        "Michael",
        "Kate",
        "Marc",
        "Stella",
        "Acne",
        "Off",
        "Fear",
        "Palace",
        "Supreme",
        "Bape",
        "Visvim",
        "Kapital",
        "Engineered",
        "Porter",
        "Head",
        "Anello",
        "Sacai",
        "Undercover",
        "Neighborhood",
        "Wtaps",
        "Fragment",
        "Human",
        "Barbour",
        "Filson",
        "Belstaff",
        "RRL",
        "Double",
        "Schott",
        "Alpha",
        "Buzz",
        "The",
        "Real",
        "McCoy",
        "BuzzRickson",
        "Toys",
        "Warehouse",
        "Freewheelers",
        "Buzz2",
        "Sugar",
        "Samurai",
        "Iron",
        "Studio",
        "Flat",
    ]
    assert count <= len(brands)
    return [
        MarketListing(
            id=f"fp-seq-{index}",
            title=f"{brands[index]} Product Model Series {index} Item SKU{index}",
            brand=brands[index],
            category="Wallet",
            condition="Excellent",
            price=Decimal(str(200 + index * 10)),
            currency="USD",
            market_name="Fashionphile",
            url=f"https://www.fashionphile.com/products/seq-item-{index}-sku{index}",
            source_type="EXISTING_IMPORT",
            created_at=now,
        )
        for index in range(count)
    ]


def test_run_batch_profit_auto_caps_above_max_without_raising(tmp_path: Path, monkeypatch) -> None:
    """Workspace 利益分析 must not 500 when >20 selected; first 20 run only."""
    from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES

    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "cap.db")
    )
    batch = service.import_existing_listings(_distinct_wallet_listings(25), name="Cap Test")
    service.select_all_eligible(batch.workspace_batch_id)
    _, before = service.get_batch(batch.workspace_batch_id)
    selected_before = sum(1 for item in before if item.selected_for_profit_check)
    assert selected_before > MAX_BATCH_CANDIDATES

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )
    run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    assert run.summary.processed_count == MAX_BATCH_CANDIDATES
    _, after = service.get_batch(batch.workspace_batch_id)
    analyzed = sum(1 for item in after if item.last_profit_checked_at)
    assert analyzed == MAX_BATCH_CANDIDATES
    still_selected = sum(1 for item in after if item.selected_for_profit_check)
    assert still_selected == MAX_BATCH_CANDIDATES


def test_repeated_profit_clicks_advance_through_unanalyzed(tmp_path: Path, monkeypatch) -> None:
    """Each 利益分析 click must analyze the next unanalyzed tranche, not the first 20 again."""
    from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES

    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "seq.db")
    )
    total = 45
    batch = service.import_existing_listings(_distinct_wallet_listings(total), name="Seq Test")
    service.select_all_eligible(batch.workspace_batch_id)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    seen_ids: list[set[str]] = []
    expected_rounds = (total + MAX_BATCH_CANDIDATES - 1) // MAX_BATCH_CANDIDATES
    for round_index in range(expected_rounds):
        _, before = service.get_batch(batch.workspace_batch_id)
        unanalyzed_before = [
            item.candidate_id
            for item in before
            if item.eligible_for_profit_check
            and not item.duplicate_of
            and not item.last_profit_checked_at
        ]
        run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
        expected_this_round = min(MAX_BATCH_CANDIDATES, len(unanalyzed_before))
        assert run.summary.processed_count == expected_this_round
        this_ids = {item.candidate.candidate_id for item in run.results}
        assert this_ids == set(unanalyzed_before[:expected_this_round])
        for prior in seen_ids:
            assert this_ids.isdisjoint(prior)
        seen_ids.append(this_ids)
        _, after = service.get_batch(batch.workspace_batch_id)
        analyzed = sum(1 for item in after if item.last_profit_checked_at)
        assert analyzed == min(total, (round_index + 1) * MAX_BATCH_CANDIDATES)

    _, final_rows = service.get_batch(batch.workspace_batch_id)
    assert sum(1 for item in final_rows if item.last_profit_checked_at) == total
    assert all(
        item.last_profit_checked_at
        for item in final_rows
        if item.eligible_for_profit_check and not item.duplicate_of
    )


def test_four_clicks_process_eighty_candidates_in_batches_of_twenty(tmp_path: Path, monkeypatch) -> None:
    """Release audit: 80 eligible candidates advance across exactly four 利益分析 clicks."""
    from marketplace.acquisition_workspace.profit_bridge import MAX_BATCH_CANDIDATES

    assert MAX_BATCH_CANDIDATES == 20
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "eighty.db")
    )
    total = 80
    batch = service.import_existing_listings(_distinct_wallet_listings(total), name="Eighty Test")
    service.select_all_eligible(batch.workspace_batch_id)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )

    seen_ids: list[set[str]] = []
    for round_index in range(4):
        _, before = service.get_batch(batch.workspace_batch_id)
        unanalyzed_before = [
            item.candidate_id
            for item in before
            if item.eligible_for_profit_check
            and not item.duplicate_of
            and not item.last_profit_checked_at
            and item.last_profit_batch_id == ""
            and item.last_gross_profit is None
            and item.last_net_profit is None
        ]
        run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
        assert run.summary.status != "already_complete"
        assert run.summary.processed_count == MAX_BATCH_CANDIDATES
        this_ids = {item.candidate.candidate_id for item in run.results}
        assert this_ids == set(unanalyzed_before[:MAX_BATCH_CANDIDATES])
        for prior in seen_ids:
            assert this_ids.isdisjoint(prior)
        seen_ids.append(this_ids)
        _, after = service.get_batch(batch.workspace_batch_id)
        analyzed = sum(1 for item in after if item.last_profit_checked_at)
        assert analyzed == (round_index + 1) * MAX_BATCH_CANDIDATES

    assert len(seen_ids) == 4
    assert sum(len(group) for group in seen_ids) == total
    _, final_rows = service.get_batch(batch.workspace_batch_id)
    assert sum(1 for item in final_rows if item.last_profit_checked_at) == total

    # Fifth click must not re-analyze; ranking fields stay intact.
    before_profits = {item.candidate_id: item.last_gross_profit for item in final_rows}
    done = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    assert done.summary.status == "already_complete"
    assert done.summary.processed_count == 0
    _, after_done = service.get_batch(batch.workspace_batch_id)
    assert {item.candidate_id: item.last_gross_profit for item in after_done} == before_profits


def test_select_all_does_not_clear_completed_analysis_flags(tmp_path: Path, monkeypatch) -> None:
    service = AcquisitionWorkspaceService(
        AcquisitionWorkspaceRepository(database_path=tmp_path / "selectall.db")
    )
    batch = service.import_existing_listings(_distinct_wallet_listings(25), name="SelectAll")
    service.select_all_eligible(batch.workspace_batch_id)
    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _fake_profit_run,
    )
    monkeypatch.setattr(
        "app.storage.batch_profit_repository.BatchProfitRepository.save_run",
        lambda self, run: None,
    )
    service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    _, mid = service.get_batch(batch.workspace_batch_id)
    analyzed_ids = {item.candidate_id for item in mid if item.last_profit_checked_at}
    assert len(analyzed_ids) == 20

    service.select_all_eligible(batch.workspace_batch_id)
    _, after_select = service.get_batch(batch.workspace_batch_id)
    assert all(
        item.last_profit_checked_at for item in after_select if item.candidate_id in analyzed_ids
    )

    run2 = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    second_ids = {item.candidate.candidate_id for item in run2.results}
    assert second_ids.isdisjoint(analyzed_ids)
    assert len(second_ids) == 5


def test_apply_profit_results_fills_empty_retrieved_at() -> None:
    candidate = make_candidate(selected=True)
    updated = apply_profit_results(
        [candidate],
        batch_id="bp-empty-ts",
        results_by_candidate_id={
            candidate.candidate_id: {
                "retrieved_at": "",
                "batch_decision": "HOLD",
                "gross_estimated_profit": "100",
                "net_estimated_profit": None,
                "warning": "",
                "yahoo_data_source": "FIXTURE",
                "net_profit_complete": False,
            }
        },
    )[0]
    assert updated.last_profit_checked_at
    assert updated.last_profit_batch_id == "bp-empty-ts"
    assert updated.last_gross_profit == Decimal("100")


def test_workspace_id_preserved_in_batch_candidate() -> None:
    candidate = make_candidate(selected=True)
    converted = to_batch_profit_candidates([candidate])[0]
    assert converted.candidate_id == candidate.candidate_id
    assert converted.purchase_source == candidate.source_name


def test_apply_profit_results_reference() -> None:
    candidate = make_candidate(selected=True)
    updated = apply_profit_results(
        [candidate],
        batch_id="bp-123",
        results_by_candidate_id={
            candidate.candidate_id: {
                "retrieved_at": "2026-01-01T00:00:00+00:00",
                "batch_decision": "HOLD",
                "gross_estimated_profit": "5000",
                "net_estimated_profit": "3000",
                "warning": "COMPARABLE_DATA_SUSPECT",
                "yahoo_data_source": "LIVE",
                "yahoo_queries": ("query-1", "query-2"),
                "candidate_count": 5,
                "comparable_count": 3,
                "estimated_from_multiple_results": True,
                "median_used": True,
                "net_profit_complete": True,
            }
        },
    )[0]
    assert updated.last_profit_batch_id == "bp-123"
    assert updated.last_decision == "HOLD"
    assert updated.last_gross_profit == Decimal("5000")
    assert updated.last_net_profit == Decimal("3000")
    assert updated.data_truth_summary.confidence_level == "HIGH"
    assert updated.discovery_metadata.runtime_mode == "LIVE"
    assert updated.discovery_metadata.query_count == 2
    assert updated.discovery_metadata.comparable_count == 3


def test_run_batch_profit_from_workspace(tmp_path, monkeypatch) -> None:
    repo = AcquisitionWorkspaceRepository(database_path=tmp_path / "ws.db")
    service = AcquisitionWorkspaceService(repo)
    batch = service.import_csv(FIXTURES / "batch_profit" / "candidates_valid.csv")
    service.select_all_eligible(batch.workspace_batch_id)

    def _inject_html(candidates, **kwargs):
        kwargs["html_by_query"] = {query: YAHOO_HTML for query in [
            "シャネル キャビアスキン 財布 黒",
            "シャネル クラシック 財布",
            "CHANEL wallet caviar black",
        ]}
        return _real_run_batch_profit(candidates, **kwargs)

    monkeypatch.setattr(
        "profit_discovery.discovery_validation.batch_profit.pipeline.run_batch_profit",
        _inject_html,
    )
    run = service.run_batch_profit(batch.workspace_batch_id, use_cache=False)
    _, candidates = service.get_batch(batch.workspace_batch_id)
    checked = [item for item in candidates if item.last_profit_batch_id]
    assert run.summary.processed_count >= 1
    assert checked
