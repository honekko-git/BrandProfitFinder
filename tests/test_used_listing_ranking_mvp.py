"""Focused tests for used listing ranking MVP."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from io import StringIO
from pathlib import Path

from marketplace.acquisition_workspace.exporters import export_candidates_csv, export_candidates_json
from marketplace.acquisition_workspace.models import ConfidenceLevel, DiscoveryMetadata
from marketplace.acquisition_workspace.ranking import (
    CONFIDENCE_SCORE_MAP,
    WEIGHT_CONFIDENCE,
    WEIGHT_DEMAND,
    WEIGHT_PROFIT,
    WEIGHT_ROI,
    build_analysis_summary,
    confidence_to_score,
    is_ranking_eligible,
    is_valid_source_listing_url,
    rank_used_listings,
    source_listing_url_warning,
)
from profit_discovery.cli.acquisition_workspace_command import run_acquisition_cli
from tests.acquisition_test_helpers import make_candidate


def _profit_ready(candidate, *, net: str, comparables: int = 3, confidence: str = "HIGH"):
    return replace(
        candidate,
        last_net_profit=Decimal(net),
        last_gross_profit=Decimal(net),
        last_profit_checked_at="2026-07-31T00:00:00+00:00",
        data_truth_summary=replace(
            candidate.data_truth_summary,
            confidence_level=confidence,
            used_estimated_price=True,
            used_estimated_shipping=True,
            shipping_source="Estimated",
        ),
        discovery_metadata=replace(
            candidate.discovery_metadata,
            comparable_count=comparables,
            candidate_count=max(comparables, 1),
        ),
    )


def test_valid_source_listing_url_rules() -> None:
    assert is_valid_source_listing_url("https://www.fashionphile.com/p/item")
    assert is_valid_source_listing_url("http://example.com/x")
    assert not is_valid_source_listing_url("")
    assert not is_valid_source_listing_url("ftp://example.com/x")
    assert not is_valid_source_listing_url("not-a-url")


def test_url_less_candidates_excluded_from_ranked_results() -> None:
    with_url = _profit_ready(make_candidate(purchase_url="https://example.com/a"), net="20000", comparables=5)
    without_url = _profit_ready(make_candidate(purchase_url=""), net="50000", comparables=8)
    ranked = rank_used_listings([with_url, without_url])
    assert len(ranked) == 1
    assert ranked[0].candidate_id == with_url.candidate_id
    assert source_listing_url_warning(without_url) == "商品ページURLが未設定または無効です"
    assert not is_ranking_eligible(without_url)


def test_confidence_mapping_and_score_range() -> None:
    assert confidence_to_score("HIGH") == Decimal("100")
    assert confidence_to_score("MEDIUM") == Decimal("60")
    assert confidence_to_score("LOW") == Decimal("25")
    assert CONFIDENCE_SCORE_MAP[ConfidenceLevel.HIGH.value] == Decimal("100")


def test_negative_profit_and_zero_roi_and_missing_sales() -> None:
    negative = _profit_ready(make_candidate(purchase_url="https://example.com/neg"), net="-1000", comparables=0)
    positive = _profit_ready(make_candidate(purchase_url="https://example.com/pos"), net="20000", comparables=4)
    ranked = rank_used_listings([negative, positive])
    by_id = {item.candidate_id: item for item in ranked}
    assert by_id[negative.candidate_id].profit_score == Decimal("0")
    assert by_id[negative.candidate_id].roi_score == Decimal("0")
    assert by_id[negative.candidate_id].demand_score == Decimal("0")
    assert "販売実績がありません" in by_id[negative.candidate_id].ranking_warnings
    for item in ranked:
        assert Decimal("0") <= item.overall_score <= Decimal("100")
        assert Decimal("0") <= item.profit_score <= Decimal("100")
        assert Decimal("0") <= item.roi_score <= Decimal("100")
        assert Decimal("0") <= item.demand_score <= Decimal("100")
        assert Decimal("0") <= item.confidence_score <= Decimal("100")


def test_fixed_weight_calculation_is_deterministic() -> None:
    a = _profit_ready(make_candidate(purchase_url="https://example.com/a", title="A"), net="10000", comparables=2, confidence="MEDIUM")
    b = _profit_ready(make_candidate(purchase_url="https://example.com/b", title="B"), net="30000", comparables=6, confidence="HIGH")
    first = rank_used_listings([a, b])
    second = rank_used_listings([b, a])
    assert [item.candidate_id for item in first] == [item.candidate_id for item in second]
    assert first[0].rank == 1
    assert first[0].overall_score == second[0].overall_score
    top = first[0]
    recomputed = (
        top.profit_score * WEIGHT_PROFIT
        + top.roi_score * WEIGHT_ROI
        + top.demand_score * WEIGHT_DEMAND
        + top.confidence_score * WEIGHT_CONFIDENCE
    ).quantize(Decimal("0.1"))
    assert top.overall_score == recomputed


def test_short_analysis_and_warnings_are_deterministic() -> None:
    candidate = _profit_ready(make_candidate(), net="25000", comparables=4, confidence="HIGH")
    ranked = rank_used_listings([candidate])[0]
    again = rank_used_listings([candidate])[0]
    assert ranked.analysis_summary == again.analysis_summary
    assert "価格の信頼性はHIGHです" in ranked.analysis_summary
    assert "buy this" not in ranked.analysis_summary.lower()
    assert "recommended purchase" not in ranked.analysis_summary.lower()
    assert "購入前に商品の状態・付属品をご確認ください" in ranked.ranking_warnings
    assert "送料は推定値です" in ranked.ranking_warnings
    assert "価格は推定値です" in ranked.ranking_warnings
    summary = build_analysis_summary(
        net_profit=None,
        roi=None,
        sales_count=0,
        confidence_level="LOW",
        average_profit=None,
        average_roi=None,
        warnings=("販売実績がありません",),
    )
    assert "利益データがありません" in summary
    assert "購入前に商品の状態・付属品をご確認ください" in summary


def test_export_includes_ranking_fields(tmp_path: Path) -> None:
    ranked_candidate = _profit_ready(make_candidate(selected=True), net="18000", comparables=5)
    excluded = _profit_ready(make_candidate(purchase_url="", selected=True), net="50000", comparables=9)
    csv_path = tmp_path / "ranked.csv"
    json_path = tmp_path / "ranked.json"
    export_candidates_csv(csv_path, [ranked_candidate, excluded])
    export_candidates_json(json_path, [ranked_candidate, excluded])
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "overall_score" in header
    assert "analysis_summary" in header
    assert "source_listing_url" in header
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload[0]["ranking"]["rank"] == 1
    assert payload[0]["ranking"]["source_listing_url"].startswith("https://")
    assert payload[1]["ranking"] is None
    assert payload[1]["ranking_exclusion_warning"] == "商品ページURLが未設定または無効です"


def test_cli_sort_overall_score(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "rank-cli.db"
    monkeypatch.setenv("BRAND_PROFIT_DB_PATH", str(db_path))
    from app.storage.acquisition_workspace_repository import AcquisitionWorkspaceRepository
    from marketplace.acquisition_workspace.models import WorkspaceBatch
    from datetime import UTC, datetime

    now = datetime.now(tz=UTC).isoformat()
    repo = AcquisitionWorkspaceRepository(database_path=db_path)
    batch = WorkspaceBatch(
        workspace_batch_id="ws-rank",
        name="Rank",
        source_type="CSV",
        created_at=now,
        updated_at=now,
        total_rows=2,
        accepted_count=2,
        warning_count=0,
        rejected_count=0,
        duplicate_count=0,
        selected_count=0,
        status="COMPLETED",
    )
    repo.save_batch(batch)
    low = _profit_ready(make_candidate(workspace_batch_id="ws-rank", title="Low Score", purchase_url="https://example.com/low"), net="1000", comparables=1, confidence="LOW")
    high = _profit_ready(make_candidate(workspace_batch_id="ws-rank", title="High Score", purchase_url="https://example.com/high"), net="40000", comparables=8, confidence="HIGH")
    repo.save_candidate(low)
    repo.save_candidate(high)
    out = StringIO()
    code = run_acquisition_cli(
        ["acquisition-list", "--workspace-batch-id", "ws-rank", "--sort", "overall-score", "--limit", "5"],
        output=out,
    )
    rendered = out.getvalue()
    assert code == 0
    assert "総合評価:" in rendered
    assert "商品ページURL:" in rendered
    assert "AI分析:" in rendered
    assert rendered.index("High Score") < rendered.index("Low Score")
