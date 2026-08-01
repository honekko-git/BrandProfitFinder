"""Browser pipeline for controlled live profit verification."""

from __future__ import annotations

from dataclasses import dataclass

from app.storage.live_acquisition_repository import LiveAcquisitionEvidenceRepository
from marketplace.browser_acquisition.models import ControlledLiveVerificationResult
from profit_discovery.discovery_validation.controlled_live_verification import (
    build_controlled_live_verifications,
)

from app.store import ValidationResultStore, ValidationSearchSnapshot


@dataclass(frozen=True, slots=True)
class ControlledLivePipelineResult:
    """Output from one controlled live verification search."""

    snapshot: ValidationSearchSnapshot
    results: list[ControlledLiveVerificationResult]
    blocking_reason: str
    result_count: int


def run_controlled_live_verification_search(
    *,
    brand: str = "Chanel",
    category: str = "Wallet",
    purchase_limit: int = 10,
    sold_limit: int = 20,
    purchase_html: str | None = None,
    yahoo_html_by_query: dict[str, str] | None = None,
) -> ControlledLivePipelineResult:
    """Run one controlled live check without silent fixture fallback."""
    results, blocking_reason = build_controlled_live_verifications(
        brand=brand,
        category=category,
        purchase_limit=purchase_limit,
        sold_limit=sold_limit,
        purchase_html=purchase_html,
        yahoo_html_by_query=yahoo_html_by_query,
    )
    snapshot = ValidationSearchSnapshot(
        brand=brand,
        category=category,
        market_mode="CONTROLLED_LIVE",
        validation_ranking=[],
        candidates_by_id={},
        real_profit_results=[],
        controlled_live_results=results,
        verification_mode="CONTROLLED_LIVE",
        blocking_reason=blocking_reason,
    )
    return ControlledLivePipelineResult(
        snapshot=snapshot,
        results=results,
        blocking_reason=blocking_reason,
        result_count=len(results),
    )


def execute_controlled_live_verification_search(
    store: ValidationResultStore,
    *,
    brand: str = "Chanel",
    category: str = "Wallet",
    purchase_limit: int = 10,
    sold_limit: int = 20,
    evidence_repository: LiveAcquisitionEvidenceRepository | None = None,
    purchase_html: str | None = None,
    yahoo_html_by_query: dict[str, str] | None = None,
) -> ControlledLivePipelineResult:
    """Execute controlled live verification, persist snapshot and evidence."""
    result = run_controlled_live_verification_search(
        brand=brand,
        category=category,
        purchase_limit=purchase_limit,
        sold_limit=sold_limit,
        purchase_html=purchase_html,
        yahoo_html_by_query=yahoo_html_by_query,
    )
    store.save(result.snapshot)
    repository = evidence_repository or LiveAcquisitionEvidenceRepository()
    for item in result.results:
        repository.save_result(item)
    return result
