"""Yahoo Auction live transport protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class YahooAuctionTransport(Protocol):
    """Contract for fetching sold Yahoo Auction listing payloads."""

    def search_sold_items(self, query: str) -> list[dict[str, object]]:
        """Return raw sold listing payloads for one search query."""


class FakeYahooAuctionTransport:
    """Deterministic transport stub for tests and offline development."""

    def __init__(
        self,
        *,
        items_by_query: dict[str, list[dict[str, object]]] | None = None,
        default_items: list[dict[str, object]] | None = None,
    ) -> None:
        self._items_by_query = items_by_query or {}
        self._default_items = list(default_items or [])

    def search_sold_items(self, query: str) -> list[dict[str, object]]:
        normalized = query.strip().lower()
        if normalized in self._items_by_query:
            return [dict(item) for item in self._items_by_query[normalized]]
        return [dict(item) for item in self._default_items]
