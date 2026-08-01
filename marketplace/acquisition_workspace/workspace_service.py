"""Acquisition workspace orchestration service."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from marketplace.acquisition_workspace.candidate_parser import (
    csv_rows_to_parsed,
    parse_manual_rows,
    read_acquisition_csv,
)
from marketplace.acquisition_workspace.deduplication import deduplicate_candidates, merge_duplicate, unmerge_duplicate
from marketplace.acquisition_workspace.models import (
    AcquisitionCandidate,
    CandidateDataStatus,
    CandidateState,
    ConfidenceLevel,
    DataTruthSummary,
    DiscoveryMetadata,
    ImportEvent,
    ParsedCandidate,
    RuntimeMode,
    SourceType,
    WorkspaceBatch,
    transition_state,
)
from marketplace.acquisition_workspace.normalization import (
    build_detection_fields,
    normalize_currency,
    normalize_title,
    normalize_url,
    purchase_price_jpy,
)
from marketplace.acquisition_workspace.profit_bridge import (
    MAX_BATCH_CANDIDATES,
    apply_profit_results,
    to_batch_profit_candidates,
)
from marketplace.acquisition_workspace.quality import score_candidate
from marketplace.acquisition_workspace.ranking import (
    UsedListingRankResult,
    order_candidates_for_display,
    rank_used_listings,
    ranking_by_candidate_id,
)
from marketplace.acquisition_workspace.saved_html_parser import parse_saved_html
from marketplace.acquisition_workspace.url_intake import intake_public_url
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries

MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_HTML_TOTAL_BYTES = 25 * 1024 * 1024


class AcquisitionWorkspaceService:
    def __init__(self, repository) -> None:
        self._repo = repository

    def import_csv(self, path: Path | str, *, name: str = "") -> WorkspaceBatch:
        rows, read_errors = read_acquisition_csv(path)
        parsed, row_errors, skipped = csv_rows_to_parsed(rows)
        batch = self._create_batch(source_type=SourceType.CSV.value, name=name or Path(path).name)
        candidates = self._build_candidates(parsed, batch.workspace_batch_id, SourceType.CSV.value, CandidateDataStatus.IMPORT.value)
        return self._finalize_batch(batch, candidates, read_errors + row_errors, skipped)

    def import_manual_rows(self, rows: list[dict[str, str]], *, name: str = "Manual Input") -> WorkspaceBatch:
        result = parse_manual_rows(rows)
        batch = self._create_batch(source_type=SourceType.MANUAL.value, name=name)
        candidates = self._build_candidates(result.candidates, batch.workspace_batch_id, SourceType.MANUAL.value, CandidateDataStatus.IMPORT.value)
        return self._finalize_batch(batch, candidates, result.errors, result.skipped_rows)

    def import_saved_html_files(self, files: list[tuple[str, str]], *, name: str = "Saved HTML") -> WorkspaceBatch:
        batch = self._create_batch(source_type=SourceType.SAVED_HTML.value, name=name)
        parsed_all: list[ParsedCandidate] = []
        errors: list[str] = []
        total_bytes = 0
        for filename, html in files:
            size = len(html.encode("utf-8"))
            total_bytes += size
            if size > MAX_HTML_BYTES:
                errors.append(f"{filename}: file exceeds 5MB limit")
                continue
            if total_bytes > MAX_HTML_TOTAL_BYTES:
                errors.append("total upload exceeds 25MB limit")
                break
            parsed, strategy, diagnostics = parse_saved_html(html, filename=filename)
            self._repo.save_event(
                ImportEvent(
                    event_id=f"evt-{uuid4().hex[:12]}",
                    workspace_batch_id=batch.workspace_batch_id,
                    candidate_id="",
                    event_type="SAVED_HTML_IMPORT",
                    parser_strategy=strategy,
                    source_filename=filename,
                    source_file_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
                    diagnostics=diagnostics,
                    created_at=datetime.now(tz=UTC).isoformat(),
                )
            )
            if not parsed:
                errors.append(f"{filename}: no candidates parsed")
                continue
            parsed_all.extend(parsed)
        candidates = self._build_candidates(
            parsed_all,
            batch.workspace_batch_id,
            SourceType.SAVED_HTML.value,
            CandidateDataStatus.PARSED_SAVED_HTML.value,
        )
        return self._finalize_batch(batch, candidates, errors, 0)

    def import_public_url(
        self,
        *,
        url: str,
        title: str,
        price: Decimal,
        currency: str,
        condition: str = "",
    ) -> WorkspaceBatch:
        batch = self._create_batch(source_type=SourceType.PUBLIC_URL.value, name="Public URL")
        parsed = [intake_public_url(url=url, title=title, price=price, currency=currency, condition=condition)]
        candidates = self._build_candidates(parsed, batch.workspace_batch_id, SourceType.PUBLIC_URL.value, CandidateDataStatus.IMPORT.value)
        return self._finalize_batch(batch, candidates, [], 0)

    def import_existing_listings(
        self,
        listings,
        *,
        name: str = "Existing Imports",
        fx_snapshot_id: str | None = None,
    ) -> WorkspaceBatch:
        from marketplace.acquisition_workspace.fx_store import load_snapshot, link_batch_to_snapshot

        batch = self._create_batch(source_type=SourceType.EXISTING_IMPORT.value, name=name)
        snapshot = load_snapshot(fx_snapshot_id or "") if fx_snapshot_id else None
        parsed = [
            ParsedCandidate(
                title=listing.title,
                brand=listing.brand,
                category=listing.category,
                condition=listing.condition,
                purchase_price=listing.price,
                currency=listing.currency,
                purchase_url=listing.url,
                source_name=listing.market_name,
                external_id=listing.id,
                image_url="",
                raw_description=(
                    f"fx_snapshot_id={snapshot.snapshot_id}" if snapshot is not None else ""
                ),
                parser_strategy=SourceType.EXISTING_IMPORT.value,
            )
            for listing in listings
        ]
        candidates = self._build_candidates(
            parsed,
            batch.workspace_batch_id,
            SourceType.EXISTING_IMPORT.value,
            CandidateDataStatus.IMPORT.value,
            fx_snapshot=snapshot,
        )
        finalized = self._finalize_batch(batch, candidates, [], 0)
        if snapshot is not None:
            link_batch_to_snapshot(finalized.workspace_batch_id, snapshot.snapshot_id)
        return finalized

    def append_existing_listings(
        self,
        workspace_batch_id: str,
        listings,
        *,
        fx_snapshot_id: str | None = None,
    ) -> WorkspaceBatch:
        """Append MarketListings to an existing batch, skipping URL duplicates already present."""
        from marketplace.acquisition_workspace.fashionphile_dom_extract import (
            canonicalize_product_url,
        )
        from marketplace.acquisition_workspace.fx_store import load_snapshot, link_batch_to_snapshot
        from marketplace.acquisition_workspace.normalization import normalize_url

        def _url_key(url: str) -> str:
            text = (url or "").strip()
            if not text:
                return ""
            try:
                return canonicalize_product_url(text)
            except ValueError:
                return normalize_url(text)

        batch, existing = self._repo.get_batch(workspace_batch_id)
        existing_urls = {_url_key(item.purchase_url) for item in existing if item.purchase_url}
        existing_urls.discard("")
        fresh = []
        for listing in listings:
            key = _url_key(getattr(listing, "url", "") or "")
            if key and key in existing_urls:
                continue
            if key:
                existing_urls.add(key)
            fresh.append(listing)
        if not fresh:
            return batch
        snapshot = load_snapshot(fx_snapshot_id or "") if fx_snapshot_id else None
        if snapshot is None and fx_snapshot_id:
            snapshot = load_snapshot(fx_snapshot_id)
        parsed = [
            ParsedCandidate(
                title=listing.title,
                brand=listing.brand,
                category=listing.category,
                condition=listing.condition,
                purchase_price=listing.price,
                currency=listing.currency,
                purchase_url=listing.url,
                source_name=listing.market_name,
                external_id=listing.id,
                image_url="",
                raw_description=(
                    f"fx_snapshot_id={snapshot.snapshot_id}" if snapshot is not None else ""
                ),
                parser_strategy=SourceType.EXISTING_IMPORT.value,
            )
            for listing in fresh
        ]
        new_candidates = self._build_candidates(
            parsed,
            workspace_batch_id,
            SourceType.EXISTING_IMPORT.value,
            CandidateDataStatus.IMPORT.value,
            fx_snapshot=snapshot,
        )
        if snapshot is not None:
            link_batch_to_snapshot(workspace_batch_id, snapshot.snapshot_id)
        # Avoid marking new rows as duplicates of each other only; cross-check existing IDs.
        existing_ids = {item.candidate_id for item in existing}
        for candidate in new_candidates:
            if candidate.duplicate_of and candidate.duplicate_of not in existing_ids:
                # within-new-set duplicates are fine
                pass
        merged = list(existing) + list(new_candidates)
        for candidate in new_candidates:
            self._repo.save_candidate(candidate)
        summary = replace(
            batch,
            updated_at=datetime.now(tz=UTC).isoformat(),
            total_rows=len(merged),
            accepted_count=sum(1 for item in merged if item.quality_grade != "REJECTED"),
            warning_count=sum(1 for item in merged if item.validation_warnings),
            rejected_count=sum(1 for item in merged if item.quality_grade == "REJECTED"),
            duplicate_count=sum(1 for item in merged if item.duplicate_of),
            selected_count=sum(1 for item in merged if item.selected_for_profit_check),
            status="OPEN",
        )
        self._repo.update_batch(summary)
        return summary

    def list_batches(self, *, limit: int = 20) -> list[WorkspaceBatch]:
        return self._repo.list_batches(limit=limit)

    def get_batch(self, workspace_batch_id: str) -> tuple[WorkspaceBatch, list[AcquisitionCandidate]]:
        return self._repo.get_batch(workspace_batch_id)

    def list_candidates(
        self,
        workspace_batch_id: str,
        *,
        eligible_only: bool = False,
        selected_only: bool = False,
    ) -> list[AcquisitionCandidate]:
        _, candidates = self._repo.get_batch(workspace_batch_id)
        if eligible_only:
            candidates = [item for item in candidates if item.eligible_for_profit_check and not item.duplicate_of]
        if selected_only:
            candidates = [item for item in candidates if item.selected_for_profit_check]
        return candidates

    def rank_candidates(self, workspace_batch_id: str) -> list[UsedListingRankResult]:
        _, candidates = self._repo.get_batch(workspace_batch_id)
        return rank_used_listings(candidates)

    def list_candidates_ranked_for_display(self, workspace_batch_id: str) -> list[AcquisitionCandidate]:
        _, candidates = self._repo.get_batch(workspace_batch_id)
        return order_candidates_for_display(candidates)

    def ranking_map(self, candidates: list[AcquisitionCandidate]) -> dict[str, UsedListingRankResult]:
        return ranking_by_candidate_id(candidates)

    def select_candidate(self, workspace_batch_id: str, candidate_id: str, selected: bool = True) -> AcquisitionCandidate:
        candidate = self._repo.get_candidate(workspace_batch_id, candidate_id)
        if candidate.duplicate_of or candidate.quality_grade == "REJECTED":
            raise ValueError("Cannot select duplicate or rejected candidate")
        state = CandidateState.SELECTED.value if selected else CandidateState.READY.value
        updated = replace(candidate, selected_for_profit_check=selected, candidate_state=state)
        self._repo.update_candidate(updated)
        return updated

    def select_all_eligible(self, workspace_batch_id: str) -> list[AcquisitionCandidate]:
        _, candidates = self._repo.get_batch(workspace_batch_id)
        updated: list[AcquisitionCandidate] = []
        for candidate in candidates:
            if candidate.eligible_for_profit_check and not candidate.duplicate_of:
                item = replace(
                    candidate,
                    selected_for_profit_check=True,
                    candidate_state=CandidateState.SELECTED.value,
                )
                self._repo.update_candidate(item)
                updated.append(item)
        return updated

    def deselect_all(self, workspace_batch_id: str) -> None:
        _, candidates = self._repo.get_batch(workspace_batch_id)
        for candidate in candidates:
            if candidate.selected_for_profit_check:
                self._repo.update_candidate(
                    replace(
                        candidate,
                        selected_for_profit_check=False,
                        candidate_state=CandidateState.READY.value,
                    )
                )

    def mark_rejected(self, workspace_batch_id: str, candidate_id: str) -> AcquisitionCandidate:
        candidate = self._repo.get_candidate(workspace_batch_id, candidate_id)
        updated = replace(
            candidate,
            candidate_state=CandidateState.REJECTED.value,
            eligible_for_profit_check=False,
            selected_for_profit_check=False,
            quality_grade="REJECTED",
        )
        self._repo.update_candidate(updated)
        return updated

    def merge_candidates(self, workspace_batch_id: str, primary_id: str, duplicate_id: str) -> None:
        primary = self._repo.get_candidate(workspace_batch_id, primary_id)
        duplicate = self._repo.get_candidate(workspace_batch_id, duplicate_id)
        _, merged = merge_duplicate(primary, duplicate)
        self._repo.update_candidate(merged)

    def unmerge_candidate(self, workspace_batch_id: str, candidate_id: str) -> AcquisitionCandidate:
        candidate = self._repo.get_candidate(workspace_batch_id, candidate_id)
        updated = unmerge_duplicate(candidate)
        self._repo.update_candidate(updated)
        return updated

    def delete_candidate(self, workspace_batch_id: str, candidate_id: str) -> None:
        self._repo.delete_candidate(workspace_batch_id, candidate_id)

    def run_batch_profit(
        self,
        workspace_batch_id: str,
        *,
        cost_profile_name: str = "standard",
        use_cache: bool = True,
        html_by_query: dict[str, str] | None = None,
        open_html_by_query: dict[str, str] | None = None,
        mercari_html_by_query: dict[str, str] | None = None,
    ):
        _, candidates = self._repo.get_batch(workspace_batch_id)

        def _eligible(item: AcquisitionCandidate) -> bool:
            return (
                item.eligible_for_profit_check
                and not item.duplicate_of
                and item.quality_grade != "REJECTED"
            )

        from marketplace.acquisition_workspace.analysis_version import is_profit_analysis_current

        def _analysis_completed(item: AcquisitionCandidate) -> bool:
            """True when a prior profit run matches the current analysis version."""
            return is_profit_analysis_current(item)

        # Next click advances through never-analyzed / outdated eligible candidates
        # (deterministic batch order). Do not re-run current-version results forever.
        unanalyzed = [item for item in candidates if _eligible(item) and not _analysis_completed(item)]
        if unanalyzed:
            tranche = unanalyzed[:MAX_BATCH_CANDIDATES]
            tranche_ids = {item.candidate_id for item in tranche}
            for item in candidates:
                if not _eligible(item):
                    continue
                want = item.candidate_id in tranche_ids
                if item.selected_for_profit_check != want:
                    self.select_candidate(
                        workspace_batch_id, item.candidate_id, selected=want
                    )
            _, candidates = self._repo.get_batch(workspace_batch_id)
        else:
            # All eligible already analyzed — do not re-run the first selected 20.
            from profit_discovery.discovery_validation.batch_profit.models import (
                BatchProfitRun,
                BatchRunSummary,
            )

            now = datetime.now(tz=UTC).isoformat()
            return BatchProfitRun(
                summary=BatchRunSummary(
                    batch_id=f"batch-complete-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}",
                    started_at=now,
                    completed_at=now,
                    total_candidates=0,
                    processed_count=0,
                    strong_candidate_count=0,
                    review_count=0,
                    hold_count=0,
                    reject_count=0,
                    failed_count=0,
                    blocked_count=0,
                    total_yahoo_requests=0,
                    cache_hits=0,
                    exchange_rate="",
                    cost_profile=cost_profile_name,
                    status="already_complete",
                ),
                results=(),
            )

        batch_candidates = to_batch_profit_candidates(candidates)
        from profit_discovery.discovery_validation.batch_profit.costs import CostProfileStore, default_cost_profiles
        from profit_discovery.discovery_validation.batch_profit.pipeline import run_batch_profit
        from app.storage.yahoo_cache_repository import YahooSearchCacheRepository

        profile = CostProfileStore(profiles=default_cost_profiles(), storage_path=Path("data/cost_profiles.json")).get(
            cost_profile_name
        )
        run = run_batch_profit(
            batch_candidates,
            cost_profile=profile,
            use_cache=use_cache,
            cache_repository=YahooSearchCacheRepository(),
            html_by_query=html_by_query,
            open_html_by_query=open_html_by_query,
            mercari_html_by_query=mercari_html_by_query,
        )
        from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION

        results_map = {
            item.candidate.candidate_id: {
                "retrieved_at": item.retrieved_at or datetime.now(tz=UTC).isoformat(),
                "batch_decision": item.batch_decision,
                "gross_estimated_profit": item.gross_estimated_profit,
                "net_estimated_profit": item.net_estimated_profit,
                "warning": ", ".join(item.warnings) if item.warnings else item.comparable_warning,
                "yahoo_data_source": item.yahoo_data_source,
                "yahoo_queries": item.yahoo_queries,
                "candidate_count": item.raw_sample_count,
                "comparable_count": item.accepted_comparable_count,
                "estimated_from_multiple_results": item.raw_sample_count > 1,
                "median_used": True,
                "net_profit_complete": item.estimated_costs.net_profit_complete,
                "profit_analysis_version": PROFIT_ANALYSIS_VERSION,
            }
            for item in run.results
        }
        updated = apply_profit_results(candidates, batch_id=run.summary.batch_id, results_by_candidate_id=results_map)
        for item in updated:
            self._repo.update_candidate(item)
        from app.storage.batch_profit_repository import BatchProfitRepository

        BatchProfitRepository().save_run(run)
        return run

    def preview_yahoo_queries(self, candidate: AcquisitionCandidate) -> tuple[str, ...]:
        from marketplace.browser_acquisition.yahoo_search_queries import MAX_SEARCH_QUERIES

        queries = build_yahoo_search_queries(
            title=candidate.title, brand=candidate.brand, category=candidate.category
        )[:MAX_SEARCH_QUERIES]
        safe = [query for query in queries if not _is_unsafe_query(query)]
        return tuple(safe)

    def _create_batch(self, *, source_type: str, name: str) -> WorkspaceBatch:
        now = datetime.now(tz=UTC).isoformat()
        batch = WorkspaceBatch(
            workspace_batch_id=f"ws-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            name=name,
            source_type=source_type,
            created_at=now,
            updated_at=now,
            total_rows=0,
            accepted_count=0,
            warning_count=0,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="OPEN",
        )
        self._repo.save_batch(batch)
        return batch

    def _build_candidates(
        self,
        parsed: list[ParsedCandidate],
        workspace_batch_id: str,
        source_type: str,
        data_status: str,
        *,
        fx_snapshot=None,
    ) -> list[AcquisitionCandidate]:
        from marketplace.acquisition_workspace.fx_convert import convert_to_jpy

        now = datetime.now(tz=UTC).isoformat()
        built: list[AcquisitionCandidate] = []
        for item in parsed:
            detection = build_detection_fields(
                title=item.title,
                brand=item.brand,
                category=item.category,
                condition=item.condition,
            )
            currency = normalize_currency(item.currency)
            score, grade, warnings, errors, eligible = score_candidate(
                title=item.title,
                brand=str(detection["brand"]),
                category=str(detection["category"]),
                detected_subtype=str(detection["detected_subtype"]),
                detected_material=str(detection["detected_material"]),
                purchase_price=item.purchase_price,
                currency=currency,
                purchase_url=item.purchase_url,
                detected_condition=str(detection["detected_condition"]),
            )
            all_warnings = tuple(dict.fromkeys((*item.warnings, *warnings)))
            truth = _build_import_truth_summary(
                source_type=source_type,
                source_name=item.source_name,
                parser_strategy=item.parser_strategy,
            )
            metadata = DiscoveryMetadata(
                discovery_timestamp=now,
                runtime_mode=RuntimeMode.IMPORT.value,
                query_count=1,
                query_used=(),
                candidate_count=1,
                comparable_count=0,
                estimated_from_multiple_results=False,
                median_used=False,
            )
            if fx_snapshot is not None:
                converted = convert_to_jpy(item.purchase_price, currency, fx_snapshot)
                price_jpy = (
                    converted
                    if converted is not None
                    else purchase_price_jpy(item.purchase_price, currency)
                )
            else:
                price_jpy = purchase_price_jpy(item.purchase_price, currency)
            candidate = AcquisitionCandidate(
                candidate_id=f"ac-{uuid4().hex[:12]}",
                workspace_batch_id=workspace_batch_id,
                title=item.title,
                normalized_title=normalize_title(item.title),
                brand=str(detection["brand"]),
                category=str(detection["category"]),
                detected_subtype=str(detection["detected_subtype"]),
                detected_material=str(detection["detected_material"]),
                detected_model_tokens=tuple(detection["detected_model_tokens"]),
                detected_color=str(detection["detected_color"]),
                detected_condition=str(detection["detected_condition"]),
                purchase_price=item.purchase_price,
                currency=currency,
                purchase_price_jpy=price_jpy,
                purchase_url=item.purchase_url,
                source_name=item.source_name,
                source_type=source_type,
                external_id=item.external_id,
                image_url=item.image_url,
                seller_name="",
                location="",
                raw_description=item.raw_description[:500],
                acquired_at=now,
                imported_at=now,
                data_status=data_status,
                quality_score=score,
                quality_grade=grade,
                validation_errors=errors,
                validation_warnings=all_warnings,
                duplicate_of="",
                duplicate_reason="",
                eligible_for_profit_check=eligible,
                selected_for_profit_check=False,
                candidate_state=CandidateState.READY.value if grade != "REJECTED" else CandidateState.REJECTED.value,
                data_truth_summary=truth,
                discovery_metadata=metadata,
            )
            preview = self.preview_yahoo_queries(candidate)
            candidate = replace(
                candidate,
                yahoo_query_preview=preview,
                discovery_metadata=replace(
                    candidate.discovery_metadata,
                    query_count=max(1, len(preview)),
                    query_used=preview,
                ),
            )
            built.append(candidate)
        return deduplicate_candidates(built)

    def _finalize_batch(
        self,
        batch: WorkspaceBatch,
        candidates: list[AcquisitionCandidate],
        errors: list[str],
        skipped: int,
    ) -> WorkspaceBatch:
        for candidate in candidates:
            self._repo.save_candidate(candidate)
        summary = replace(
            batch,
            updated_at=datetime.now(tz=UTC).isoformat(),
            total_rows=len(candidates),
            accepted_count=sum(1 for item in candidates if item.quality_grade != "REJECTED"),
            warning_count=sum(1 for item in candidates if item.validation_warnings),
            rejected_count=sum(1 for item in candidates if item.quality_grade == "REJECTED"),
            duplicate_count=sum(1 for item in candidates if item.duplicate_of),
            selected_count=0,
            status="COMPLETED",
        )
        self._repo.update_batch(summary)
        if errors:
            self._repo.save_event(
                ImportEvent(
                    event_id=f"evt-{uuid4().hex[:12]}",
                    workspace_batch_id=batch.workspace_batch_id,
                    candidate_id="",
                    event_type="IMPORT_WARNINGS",
                    parser_strategy="",
                    source_filename="",
                    source_file_hash="",
                    diagnostics={"errors": errors, "skipped": skipped},
                    created_at=datetime.now(tz=UTC).isoformat(),
                )
            )
        return summary


def _is_unsafe_query(query: str) -> bool:
    tokens = set(query.lower().split())
    if tokens <= {"chanel", "wallet", "財布", "シャネル"}:
        return True
    return len(query.strip()) < 4


def _build_import_truth_summary(*, source_type: str, source_name: str, parser_strategy: str) -> DataTruthSummary:
    reasons = [_format_source_reason(source_type)]
    if parser_strategy and parser_strategy != source_type:
        reasons.append(parser_strategy.replace("_", " ").title())
    return DataTruthSummary(
        source_mode=RuntimeMode.IMPORT.value,
        acquisition_mode=source_type,
        market_source=source_name or source_type.title(),
        price_source=_format_price_source(source_type),
        comparable_source="Not Run",
        shipping_source="Not Run",
        fee_source="Not Run",
        used_live_data=False,
        used_fixture_data=False,
        used_saved_html=source_type == SourceType.SAVED_HTML.value,
        used_manual_input=source_type == SourceType.MANUAL.value,
        used_estimated_price=False,
        used_estimated_shipping=False,
        confidence_level=_initial_confidence(source_type),
        reasons=tuple(reasons),
    )


def _format_source_reason(source_type: str) -> str:
    labels = {
        SourceType.MANUAL.value: "Manual Listing",
        SourceType.CSV.value: "CSV Import",
        SourceType.SAVED_HTML.value: "Saved HTML",
        SourceType.PUBLIC_URL.value: "Public URL",
        SourceType.EXISTING_IMPORT.value: "Existing Import",
        SourceType.FIXTURE.value: "Fixture Source",
    }
    return labels.get(source_type, source_type.replace("_", " ").title())


def _format_price_source(source_type: str) -> str:
    if source_type == SourceType.MANUAL.value:
        return "Manual Listing"
    if source_type == SourceType.SAVED_HTML.value:
        return "Saved HTML Listing"
    return "Imported Listing"


def _initial_confidence(source_type: str) -> str:
    if source_type in {SourceType.MANUAL.value, SourceType.PUBLIC_URL.value}:
        return ConfidenceLevel.MEDIUM.value
    if source_type == SourceType.SAVED_HTML.value:
        return ConfidenceLevel.MEDIUM.value
    return ConfidenceLevel.HIGH.value
