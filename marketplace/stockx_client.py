"""
StockX client protocol and fake client for fixture-based data.
"""

from copy import deepcopy
from typing import Protocol, runtime_checkable


@runtime_checkable
class StockXClientProtocol(Protocol):
    """Protocol for StockX search clients."""

    def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Search StockX listings from a configured data source.

        Returns:
            Parsed JSON in BrandProfitFinder internal StockX standard format.
        """
        ...


class FakeStockXClient:
    """In-memory StockX client for tests and demo mode."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        pages: dict[int, dict[str, object]] | None = None,
        error: Exception | None = None,
        *,
        filter_by_query: bool = False,
    ) -> None:
        if pages is not None:
            self._pages = {key: deepcopy(value) for key, value in pages.items()}
        elif payload is not None:
            self._pages = {1: deepcopy(payload)}
        else:
            self._pages = {1: {"marketplace": "stockx", "items": [], "total": 0, "page": 1}}
        self.error = error
        self.filter_by_query = filter_by_query
        self.last_query: str = ""
        self.last_page: int = 1
        self.last_page_size: int | None = None
        self.last_filters: dict[str, object] | None = None
        self.call_count: int = 0

    def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.call_count += 1
        self.last_query = query
        self.last_page = page
        self.last_page_size = page_size
        self.last_filters = deepcopy(filters) if filters is not None else None
        if self.error is not None:
            raise self.error
        empty: dict[str, object] = {
            "marketplace": "stockx",
            "items": [],
            "total": 0,
            "page": page,
        }
        payload = deepcopy(self._pages.get(page, empty))
        if self.filter_by_query and query.strip():
            items = payload.get("items")
            if isinstance(items, list):
                needle = query.strip().lower()
                filtered = [
                    item
                    for item in items
                    if isinstance(item, dict) and _fixture_matches_query(item, needle)
                ]
                payload["items"] = filtered
                payload["total"] = len(filtered)
        return payload

    def set_payload(self, payload: dict[str, object]) -> None:
        self._pages = {1: deepcopy(payload)}

    def set_pages(self, pages: dict[int, dict[str, object]]) -> None:
        self._pages = {key: deepcopy(value) for key, value in pages.items()}

    def set_error(self, error: Exception | None) -> None:
        self.error = error


def _fixture_matches_query(item: dict[str, object], needle: str) -> bool:
    fields = [
        str(item.get("title") or "").lower(),
        str(item.get("brand") or "").lower(),
        str(item.get("style_code") or "").lower(),
        str(item.get("sku") or "").lower(),
        str(item.get("model_number") or "").lower(),
        str(item.get("model") or "").lower(),
    ]
    return any(
        field and (needle in field or field in needle)
        for field in fields
    )
