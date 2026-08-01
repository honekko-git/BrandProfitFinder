"""Fashionphile live keyword search → acquisition workspace intake.

Minimal usable product path: retrieve raw overseas listings, normalize,
convert to JPY via existing import, then hand off to existing profit pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError
from marketplace.browser_acquisition.fashionphile_acquirer import (
    FashionphileAcquirer,
    acquired_listing_to_market_listing,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus

# Keep auto-profit bounded for daily sourcing (Yahoo comps are slow).
_AUTO_PROFIT_CAP = 5


@dataclass(frozen=True, slots=True)
class LiveFashionphileIntakeResult:
    """Outcome of one Fashionphile keyword intake."""

    batch_id: str
    query: str
    listing_count: int
    status: str
    detail: str = ""
    errors: tuple[str, ...] = ()
    first_candidate_id: str = ""
    profit_checked: bool = False


def search_fashionphile_listings(
    keyword: str,
    *,
    limit: int = 20,
    html: str | None = None,
    acquirer: FashionphileAcquirer | None = None,
) -> tuple[list[AcquiredListing], str, str]:
    """Search Fashionphile by keyword and return normalized listings.

    Returns (listings, status, detail).
    """
    query = str(keyword or "").strip()
    if not query:
        return [], AcquisitionStatus.FAILED.value, "keyword is required"

    client = acquirer or FashionphileAcquirer(purchase_limit=max(1, int(limit)))
    try:
        result = client.search_keyword(query, html=html, limit=limit)
    except AcquisitionBlockedError as exc:
        return [], AcquisitionStatus.BLOCKED.value, str(exc)
    except Exception as exc:  # noqa: BLE001 - surface live failures to UI
        return [], AcquisitionStatus.FAILED.value, str(exc)

    return list(result.listings), result.status.value, result.detail or ""


def import_fashionphile_keyword(
    service,
    keyword: str,
    *,
    limit: int = 20,
    html: str | None = None,
    acquirer: FashionphileAcquirer | None = None,
    run_profit: bool = True,
    html_by_query: dict[str, str] | None = None,
) -> LiveFashionphileIntakeResult:
    """Search Fashionphile, import listings, and run existing profit calculation."""
    listings, status, detail = search_fashionphile_listings(
        keyword,
        limit=limit,
        html=html,
        acquirer=acquirer,
    )
    query = str(keyword or "").strip()
    if not listings:
        return LiveFashionphileIntakeResult(
            batch_id="",
            query=query,
            listing_count=0,
            status=status,
            detail=detail or "No Fashionphile listings found",
            errors=(detail or "No Fashionphile listings found",),
        )

    market_listings = [acquired_listing_to_market_listing(item) for item in listings]
    batch = service.import_existing_listings(
        market_listings,
        name=f"Fashionphile LIVE: {query}",
    )
    batch_id = batch.workspace_batch_id
    _, rows = service.get_batch(batch_id)
    first_id = rows[0].candidate_id if rows else ""

    profit_checked = False
    if run_profit and rows:
        service.select_all_eligible(batch_id)
        _, selected_rows = service.get_batch(batch_id)
        extras = [item for item in selected_rows if item.selected_for_profit_check][_AUTO_PROFIT_CAP:]
        for item in extras:
            service.select_candidate(batch_id, item.candidate_id, selected=False)
        service.run_batch_profit(
            batch_id,
            use_cache=True,
            html_by_query=html_by_query,
        )
        profit_checked = True
        _, rows = service.get_batch(batch_id)
        first_id = next(
            (item.candidate_id for item in rows if item.last_profit_checked_at),
            first_id,
        )

    return LiveFashionphileIntakeResult(
        batch_id=batch_id,
        query=query,
        listing_count=len(market_listings),
        status=status,
        detail=detail,
        first_candidate_id=first_id,
        profit_checked=profit_checked,
    )
