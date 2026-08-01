"""SQLite-backed Yahoo search result cache."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from marketplace.browser_acquisition.models import AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_diagnostics import YahooParseDiagnostics

DEFAULT_CACHE_TTL_HOURS = 24


def resolve_cache_ttl_hours() -> int:
    raw = os.getenv("YAHOO_SEARCH_CACHE_TTL_HOURS", str(DEFAULT_CACHE_TTL_HOURS))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_CACHE_TTL_HOURS


@dataclass(frozen=True, slots=True)
class YahooCacheEntry:
    """One cached Yahoo search result."""

    normalized_query: str
    source: str
    retrieved_at: str
    expires_at: str
    acquisition_status: str
    raw_sample_count: int
    samples: tuple[YahooSoldSample, ...]
    diagnostics: tuple[YahooParseDiagnostics, ...]


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def serialize_samples(samples: list[YahooSoldSample]) -> str:
    payload = [
        {
            "title": sample.title,
            "sold_price_jpy": sample.sold_price_jpy,
            "retrieved_at": sample.retrieved_at,
            "source": sample.source,
            "sold_at": sample.sold_at,
            "condition": sample.condition,
            "url": sample.url,
        }
        for sample in samples
    ]
    return json.dumps(payload, ensure_ascii=False)


def deserialize_samples(raw: str) -> list[YahooSoldSample]:
    payload = json.loads(raw)
    return [
        YahooSoldSample(
            title=item["title"],
            sold_price_jpy=int(item["sold_price_jpy"]),
            retrieved_at=item.get("retrieved_at", ""),
            source=item.get("source", "Yahoo Auction"),
            sold_at=item.get("sold_at", ""),
            condition=item.get("condition", ""),
            url=item.get("url", ""),
        )
        for item in payload
    ]


def serialize_diagnostics(diagnostics: list[YahooParseDiagnostics]) -> str:
    return json.dumps([item.to_display() for item in diagnostics], ensure_ascii=False)


def deserialize_diagnostics(raw: str) -> list[YahooParseDiagnostics]:
    from marketplace.browser_acquisition.yahoo_diagnostics import YahooParseDiagnostics

    payload = json.loads(raw)
    diagnostics: list[YahooParseDiagnostics] = []
    for item in payload:
        diagnostics.append(
            YahooParseDiagnostics(
                final_url=item.get("final_url", ""),
                http_status=int(item.get("http_status", 0)),
                page_title=item.get("page_title", ""),
                result_container_count=int(item.get("result_container_count", 0)),
                price_text_count=int(item.get("price_text_count", 0)),
                parser_strategy=item.get("parser_strategy", ""),
                blocking_reason=item.get("blocking_reason", ""),
                search_query=item.get("search_query", ""),
            )
        )
    return diagnostics


def cache_age_hours(retrieved_at: str) -> float:
    retrieved = datetime.fromisoformat(retrieved_at)
    delta = datetime.now(tz=UTC) - retrieved
    return round(delta.total_seconds() / 3600, 2)


def is_cache_valid(expires_at: str) -> bool:
    return datetime.fromisoformat(expires_at) > datetime.now(tz=UTC)


def build_cache_entry(
    *,
    query: str,
    samples: list[YahooSoldSample],
    diagnostics: list[YahooParseDiagnostics],
    acquisition_status: str = AcquisitionStatus.LIVE.value,
    ttl_hours: int | None = None,
) -> YahooCacheEntry:
    now = datetime.now(tz=UTC)
    ttl = ttl_hours if ttl_hours is not None else resolve_cache_ttl_hours()
    return YahooCacheEntry(
        normalized_query=normalize_query(query),
        source="Yahoo Auction",
        retrieved_at=now.isoformat(),
        expires_at=(now + timedelta(hours=ttl)).isoformat(),
        acquisition_status=acquisition_status,
        raw_sample_count=len(samples),
        samples=tuple(samples),
        diagnostics=tuple(diagnostics),
    )
