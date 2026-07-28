"""
Vestiaire Collective client protocol and fake client for fixture-based data.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VestiaireClientProtocol(Protocol):
    """Protocol for Vestiaire Collective search clients."""

    def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Search Vestiaire listings from a configured data source.

        Args:
            query: Search keywords.
            page: Page number (1-based).
            page_size: Results per page.
            filters: Optional search filters.

        Returns:
            Parsed JSON in BrandProfitFinder internal Vestiaire standard format.
        """
        ...


class FakeVestiaireClient:
    """In-memory Vestiaire client for tests and demo mode."""

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
            self._pages = dict(pages)
        elif payload is not None:
            self._pages = {1: payload}
        else:
            self._pages = {1: {"marketplace": "vestiaire", "items": [], "total": 0, "page": 1}}
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
        self.last_filters = dict(filters) if filters else None
        if self.error is not None:
            raise self.error
        return dict(self._pages.get(page, {"marketplace": "vestiaire", "items": [], "total": 0, "page": page}))

    def set_payload(self, payload: dict[str, object]) -> None:
        """Replace single-page response payload."""
        self._pages = {1: payload}

    def set_pages(self, pages: dict[int, dict[str, object]]) -> None:
        """Replace multi-page response payloads."""
        self._pages = dict(pages)

    def set_error(self, error: Exception | None) -> None:
        """Set or clear an injected error."""
        self.error = error
