"""Vestiaire Collective live keyword search → acquisition workspace intake.

Vestiaire Collective is an overseas acquisition source. Yahoo! Auctions and
Mercari remain domestic selling-price comparables via the existing batch profit pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus
from marketplace.browser_acquisition.vestiaire_acquirer import (
    VestiaireAcquirer,
    acquired_listing_to_market_listing,
)
from marketplace.acquisition_workspace.normalization import is_supported_currency

_AUTO_PROFIT_CAP = 5


@dataclass(frozen=True, slots=True)
class LiveVestiaireIntakeResult:
    """Outcome of one Vestiaire Collective keyword intake."""

    batch_id: str
    query: str
    listing_count: int
    status: str
    detail: str = ""
    errors: tuple[str, ...] = ()
    first_candidate_id: str = ""
    profit_checked: bool = False


def search_vestiaire_listings(
    keyword: str,
    *,
    limit: int = 20,
    html: str | None = None,
    acquirer: VestiaireAcquirer | None = None,
) -> tuple[list[AcquiredListing], str, str]:
    """Search Vestiaire by keyword and return listings with product URLs."""
    query = str(keyword or "").strip()
    if not query:
        return [], AcquisitionStatus.FAILED.value, "keyword is required"

    client = acquirer or VestiaireAcquirer(purchase_limit=max(1, int(limit)))
    try:
        result = client.search_keyword(query, html=html, limit=limit)
    except AcquisitionBlockedError as exc:
        return [], AcquisitionStatus.BLOCKED.value, str(exc)
    except Exception as exc:  # noqa: BLE001 - surface live failures to UI
        return [], AcquisitionStatus.FAILED.value, str(exc)

    valid = [
        item
        for item in result.listings
        if item.url
        and item.url.startswith("http")
        and ".shtml" in item.url
        and item.price > 0
        and is_supported_currency(item.currency)
    ]
    if result.listings and not valid:
        return (
            [],
            AcquisitionStatus.FAILED.value,
            "Vestiaire Collective listings missing required product URL, price, or supported currency",
        )
    return valid, result.status.value, result.detail or ""


def import_vestiaire_keyword(
    service,
    keyword: str,
    *,
    limit: int = 20,
    html: str | None = None,
    acquirer: VestiaireAcquirer | None = None,
    run_profit: bool = True,
    html_by_query: dict[str, str] | None = None,
    mercari_html_by_query: dict[str, str] | None = None,
    open_html_by_query: dict[str, str] | None = None,
) -> LiveVestiaireIntakeResult:
    """Search Vestiaire, import listings, and run existing profit calculation."""
    listings, status, detail = search_vestiaire_listings(
        keyword,
        limit=limit,
        html=html,
        acquirer=acquirer,
    )
    query = str(keyword or "").strip()
    if not listings:
        return LiveVestiaireIntakeResult(
            batch_id="",
            query=query,
            listing_count=0,
            status=status,
            detail=detail or "No Vestiaire Collective listings found",
            errors=(detail or "No Vestiaire Collective listings found",),
        )

    market_listings = [acquired_listing_to_market_listing(item) for item in listings]
    market_listings = [item for item in market_listings if item.url and item.url.startswith("http")]
    if not market_listings:
        return LiveVestiaireIntakeResult(
            batch_id="",
            query=query,
            listing_count=0,
            status=AcquisitionStatus.FAILED.value,
            detail="Vestiaire Collective listings missing required product URL",
            errors=("Vestiaire Collective listings missing required product URL",),
        )

    batch = service.import_existing_listings(
        market_listings,
        name=f"Vestiaire Collective LIVE: {query}",
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
            mercari_html_by_query=mercari_html_by_query,
            open_html_by_query=open_html_by_query,
        )
        profit_checked = True
        _, rows = service.get_batch(batch_id)
        first_id = next(
            (item.candidate_id for item in rows if item.last_profit_checked_at),
            first_id,
        )

    return LiveVestiaireIntakeResult(
        batch_id=batch_id,
        query=query,
        listing_count=len(market_listings),
        status=status,
        detail=detail,
        first_candidate_id=first_id,
        profit_checked=profit_checked,
    )
