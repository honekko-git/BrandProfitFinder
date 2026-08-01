"""Candidate deduplication."""

from __future__ import annotations

import difflib
from dataclasses import replace

from marketplace.acquisition_workspace.models import AcquisitionCandidate, CandidateState
from marketplace.acquisition_workspace.normalization import normalize_url


def deduplicate_candidates(candidates: list[AcquisitionCandidate]) -> list[AcquisitionCandidate]:
    """Mark duplicate candidates without deleting them."""
    primaries: dict[str, str] = {}
    updated: list[AcquisitionCandidate] = []

    for candidate in candidates:
        primary_id, reason = _find_duplicate(candidate, primaries, updated)
        if primary_id:
            updated.append(
                replace(
                    candidate,
                    duplicate_of=primary_id,
                    duplicate_reason=reason,
                    candidate_state=CandidateState.DUPLICATE.value,
                    eligible_for_profit_check=False,
                    selected_for_profit_check=False,
                )
            )
            continue
        primaries[_primary_key(candidate)] = candidate.candidate_id
        updated.append(candidate)
    return updated


def merge_duplicate(primary: AcquisitionCandidate, duplicate: AcquisitionCandidate) -> tuple[AcquisitionCandidate, AcquisitionCandidate]:
    merged_duplicate = replace(
        duplicate,
        duplicate_of=primary.candidate_id,
        duplicate_reason="manual merge",
        candidate_state=CandidateState.DUPLICATE.value,
        eligible_for_profit_check=False,
        selected_for_profit_check=False,
    )
    return primary, merged_duplicate


def unmerge_duplicate(candidate: AcquisitionCandidate) -> AcquisitionCandidate:
    return replace(
        candidate,
        duplicate_of="",
        duplicate_reason="",
        candidate_state=CandidateState.READY.value if candidate.quality_grade != "REJECTED" else CandidateState.REJECTED.value,
        eligible_for_profit_check=candidate.quality_grade in {"A", "B", "C"} and not candidate.validation_errors,
    )


def _find_duplicate(
    candidate: AcquisitionCandidate,
    primaries: dict[str, str],
    existing: list[AcquisitionCandidate],
) -> tuple[str, str]:
    url_key = normalize_url(candidate.purchase_url)
    if url_key and url_key in primaries:
        return primaries[url_key], "duplicate URL"

    if candidate.external_id and candidate.source_name:
        ext_key = f"{candidate.source_name}:{candidate.external_id}"
        if ext_key in primaries:
            return primaries[ext_key], "duplicate external ID"

    signature = f"{candidate.normalized_title}|{candidate.purchase_price}|{candidate.currency}"
    if signature in primaries:
        return primaries[signature], "duplicate title+price"

    for other in existing:
        if other.candidate_id == candidate.candidate_id:
            continue
        ratio = difflib.SequenceMatcher(None, candidate.normalized_title, other.normalized_title).ratio()
        if (
            ratio >= 0.92
            and candidate.purchase_price == other.purchase_price
            and candidate.currency == other.currency
            and candidate.source_name == other.source_name
        ):
            return other.candidate_id, "high title similarity"
    return "", ""


def _primary_key(candidate: AcquisitionCandidate) -> str:
    url_key = normalize_url(candidate.purchase_url)
    if url_key:
        return url_key
    if candidate.external_id and candidate.source_name:
        return f"{candidate.source_name}:{candidate.external_id}"
    return f"{candidate.normalized_title}|{candidate.purchase_price}|{candidate.currency}"
