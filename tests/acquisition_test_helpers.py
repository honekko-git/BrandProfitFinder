"""Shared helpers for acquisition workspace tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from marketplace.acquisition_workspace.models import (
    AcquisitionCandidate,
    CandidateDataStatus,
    CandidateState,
    ConfidenceLevel,
    DataTruthSummary,
    DiscoveryMetadata,
    RuntimeMode,
    SourceType,
)


def make_candidate(
    *,
    title: str = "Chanel Classic Wallet Black Caviar",
    brand: str = "Chanel",
    category: str = "Wallet",
    purchase_price: Decimal = Decimal("695"),
    currency: str = "USD",
    purchase_url: str = "https://www.fashionphile.com/p/chanel-classic-wallet",
    source_name: str = "Fashionphile",
    source_type: str = SourceType.CSV.value,
    external_id: str = "",
    quality_grade: str = "A",
    quality_score: int = 90,
    eligible: bool = True,
    selected: bool = False,
    duplicate_of: str = "",
    data_status: str = CandidateDataStatus.IMPORT.value,
    workspace_batch_id: str = "ws-test",
) -> AcquisitionCandidate:
    now = datetime.now(tz=UTC).isoformat()
    return AcquisitionCandidate(
        candidate_id=f"ac-{uuid4().hex[:12]}",
        workspace_batch_id=workspace_batch_id,
        title=title,
        normalized_title=title.lower(),
        brand=brand,
        category=category,
        detected_subtype="COMPACT_WALLET",
        detected_material="Caviar",
        detected_model_tokens=("classic",),
        detected_color="black",
        detected_condition="EXCELLENT",
        purchase_price=purchase_price,
        currency=currency,
        purchase_price_jpy=Decimal("104250"),
        purchase_url=purchase_url,
        source_name=source_name,
        source_type=source_type,
        external_id=external_id,
        image_url="",
        seller_name="",
        location="",
        raw_description="",
        acquired_at=now,
        imported_at=now,
        data_status=data_status,
        quality_score=quality_score,
        quality_grade=quality_grade,
        validation_errors=(),
        validation_warnings=(),
        duplicate_of=duplicate_of,
        duplicate_reason="",
        eligible_for_profit_check=eligible,
        selected_for_profit_check=selected,
        candidate_state=CandidateState.READY.value,
        data_truth_summary=DataTruthSummary(
            source_mode=RuntimeMode.IMPORT.value,
            acquisition_mode=source_type,
            market_source=source_name,
            price_source="Imported Listing",
            confidence_level=ConfidenceLevel.HIGH.value,
            reasons=("CSV Import",),
        ),
        discovery_metadata=DiscoveryMetadata(
            discovery_timestamp=now,
            runtime_mode=RuntimeMode.IMPORT.value,
            query_count=1,
            query_used=("chanel wallet",),
            candidate_count=1,
            comparable_count=0,
            estimated_from_multiple_results=False,
            median_used=False,
        ),
    )
