"""Yahoo Auction live sold resolution for manual-import profit verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from marketplace.browser_acquisition.comparable_matching import (
    evaluate_comparables,
    format_comparable_diagnostics,
)
from marketplace.browser_acquisition.models import AcquiredListing, AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_diagnostics import YahooParseDiagnostics
from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries
from marketplace.browser_acquisition.yahoo_sold_acquirer import YahooSoldAcquirer
from marketplace.connectors.models import MarketListing
from profit_discovery.discovery_validation.real_profit_models import DataStatus, DomesticSoldSummary

PROVISIONAL_PREFIX = "PROVISIONAL "


@dataclass(frozen=True, slots=True)
class YahooLiveDomesticResolution:
    """Resolved Yahoo live domestic sold data for one manual import."""

    domestic: DomesticSoldSummary
    queries: tuple[str, ...]
    diagnostics: tuple[YahooParseDiagnostics, ...]
    live_sample_count: int
    matched_count: int
    rejected_count: int
    matched_samples: tuple[YahooSoldSample, ...]
    matching_score: float
    reliability: str
    purchase_subtype: str = ""
    purchase_material: str = ""
    comparable_diagnostics: str = ""
    legacy_median_jpy: Decimal = Decimal("0")
    comparable_data_warning: str = ""
    outlier_exclusions: tuple[str, ...] = ()


def resolve_yahoo_live_domestic_summary(
    *,
    listing: MarketListing,
    brand: str,
    category: str,
    html_by_query: dict[str, str] | None = None,
    yahoo_acquirer: YahooSoldAcquirer | None = None,
) -> YahooLiveDomesticResolution:
    """Resolve Yahoo live sold summary for one manual-import purchase listing."""
    acquirer = yahoo_acquirer or YahooSoldAcquirer()
    queries = build_yahoo_search_queries(title=listing.title, brand=brand, category=category)
    samples, used_queries, diagnostics = acquirer.acquire_multi(
        title=listing.title,
        brand=brand,
        category=category,
        queries=queries,
        html_by_query=html_by_query,
    )
    purchase = _listing_to_acquired(listing)
    purchase_jpy = listing.price
    if listing.currency.upper() != "JPY":
        from profit_discovery.discovery_validation.real_profit_config import resolve_usd_jpy_exchange_rate

        purchase_jpy = listing.price * Decimal(str(resolve_usd_jpy_exchange_rate()))
    comparable = evaluate_comparables(
        purchase,
        samples,
        purchase_price_jpy=purchase_jpy,
    )
    listing_url = _closed_search_url(used_queries[0] if used_queries else queries[0])
    retrieved_at = datetime.now(tz=UTC).isoformat()
    actual_source = DataStatus.LIVE.value if samples else DataStatus.UNAVAILABLE.value
    domestic = DomesticSoldSummary(
        market_name="Yahoo Auction",
        sample_count=comparable.sample_count,
        average_price_jpy=comparable.average_jpy,
        median_price_jpy=comparable.median_jpy,
        listing_url=listing_url,
        actual_source=actual_source,
        fallback_used=False,
        retrieved_at=retrieved_at,
    )
    best_score = 0.0
    if comparable.accepted_diagnostics:
        best_score = float(max(item.matching_score for item in comparable.accepted_diagnostics))
    return YahooLiveDomesticResolution(
        domestic=domestic,
        queries=tuple(used_queries),
        diagnostics=tuple(diagnostics),
        live_sample_count=len(samples),
        matched_count=comparable.sample_count,
        rejected_count=comparable.rejected_count,
        matched_samples=comparable.matched_samples,
        matching_score=best_score,
        reliability=comparable.reliability.value,
        purchase_subtype=comparable.purchase_subtype,
        purchase_material=comparable.purchase_material,
        comparable_diagnostics=format_comparable_diagnostics(comparable),
        legacy_median_jpy=comparable.legacy_median_jpy,
        comparable_data_warning=comparable.data_warning,
        outlier_exclusions=comparable.outlier_exclusions,
    )


def format_rejected_samples(comparable_diagnostics: str) -> str:
    """Format rejected comparable samples for browser display."""
    if not comparable_diagnostics:
        return ""
    payload = json.loads(comparable_diagnostics)
    rejected = payload.get("rejected", [])
    parts = [
        f"{item['title']} ({item['price_jpy']:,} JPY) [{', '.join(item.get('reasons', []))}]"
        for item in rejected[:5]
    ]
    return " | ".join(parts)


def format_accepted_comparables(comparable_diagnostics: str) -> str:
    """Format accepted comparable samples for browser display."""
    if not comparable_diagnostics:
        return ""
    payload = json.loads(comparable_diagnostics)
    accepted = payload.get("accepted", [])
    parts = [f"{item['title']} ({item['price_jpy']:,} JPY)" for item in accepted[:8]]
    return " | ".join(parts)


def format_diagnostics(diagnostics: list[YahooParseDiagnostics]) -> str:
    """Serialize diagnostics for browser display."""
    return json.dumps([item.to_display() for item in diagnostics], ensure_ascii=False)

def format_sample_titles(matched_samples: tuple) -> str:
    titles = [sample.title for sample in matched_samples[:5]]
    return " | ".join(titles)


def format_sold_prices(matched_samples: tuple) -> str:
    prices = [f"{sample.sold_price_jpy:,}" for sample in matched_samples[:5]]
    return ", ".join(prices)


def apply_provisional_decision(decision: str, *, reliability: str, matched_count: int) -> str:
    if matched_count >= 3 and reliability != "LOW":
        return decision
    if decision.startswith(PROVISIONAL_PREFIX):
        return decision
    return f"{PROVISIONAL_PREFIX}{decision}"


def _listing_to_acquired(listing: MarketListing) -> AcquiredListing:
    return AcquiredListing(
        external_id=listing.id,
        title=listing.title,
        brand=listing.brand,
        category=listing.category,
        condition=listing.condition,
        price=listing.price,
        currency=listing.currency,
        url=listing.url,
        retrieved_at=listing.created_at.isoformat(),
        source=listing.market_name,
        raw_title=listing.title,
        acquisition_status=AcquisitionStatus.LIVE,
    )


def _closed_search_url(query: str) -> str:
    from urllib.parse import quote_plus

    return f"https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={quote_plus(query.strip())}"
