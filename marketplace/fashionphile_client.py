"""
Fashionphile client protocol and fake client for fixture-based data.
"""

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FashionphileClientProtocol(Protocol):
    """Protocol for Fashionphile search clients."""

    def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Search Fashionphile listings from a configured data source.

        Args:
            query: Search keywords.
            page: Page number (1-based).
            page_size: Results per page.
            filters: Optional search filters.

        Returns:
            Parsed JSON in BrandProfitFinder internal Fashionphile standard format.
        """
        ...


class FakeFashionphileClient:
    """In-memory Fashionphile client for tests and demo mode."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        pages: dict[int, dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        """
        Initialize fake client with optional payload or multi-page payloads.

        Args:
            payload: Single-page JSON response.
            pages: Mapping of page number to JSON response.
            error: Optional exception to raise on search.
        """
        if pages is not None:
            self._pages = {key: deepcopy(value) for key, value in pages.items()}
        elif payload is not None:
            self._pages = {1: deepcopy(payload)}
        else:
            self._pages = {
                1: {"marketplace": "fashionphile", "items": [], "total": 0, "page": 1}
            }
        self.error = error
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
        """Return injected payload and record call parameters."""
        self.call_count += 1
        self.last_query = query
        self.last_page = page
        self.last_page_size = page_size
        self.last_filters = deepcopy(filters) if filters is not None else None
        if self.error is not None:
            raise self.error
        empty: dict[str, object] = {
            "marketplace": "fashionphile",
            "items": [],
            "total": 0,
            "page": page,
        }
        page_payload = self._pages.get(page, empty)
        return deepcopy(page_payload)

    def set_payload(self, payload: dict[str, object]) -> None:
        """Replace single-page response payload."""
        self._pages = {1: deepcopy(payload)}

    def set_pages(self, pages: dict[int, dict[str, object]]) -> None:
        """Replace multi-page response payloads."""
        self._pages = {key: deepcopy(value) for key, value in pages.items()}

    def set_error(self, error: Exception | None) -> None:
        """Set or clear an injected error."""
        self.error = error
