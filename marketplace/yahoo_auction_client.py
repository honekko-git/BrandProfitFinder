"""
Yahoo Auction client protocol and fake client for fixture-based data.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class YahooAuctionClientProtocol(Protocol):
    """Protocol for Yahoo Auction search clients."""

    def search_items(
        self,
        *,
        query: str,
        hits: int | None = None,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """
        Search Yahoo Auction listings from a configured data source.

        Args:
            query: Search keywords.
            hits: Maximum number of results.
            page: Page number (1-based).
            sort: Sort order.

        Returns:
            Parsed JSON response in the internal standard format.
        """
        ...


class FakeYahooAuctionClient:
    """In-memory Yahoo Auction client for tests and demo mode."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        """
        Initialize fake client with optional payload or injected error.

        Args:
            payload: JSON response returned by search_items.
            error: Optional exception to raise on search.
        """
        self.payload = payload or {
            "total_results": 0,
            "page": 1,
            "page_count": 0,
            "items": [],
        }
        self.error = error
        self.last_query: str = ""
        self.last_hits: int | None = None
        self.last_page: int = 1
        self.last_sort: str | None = None

    def search_items(
        self,
        *,
        query: str,
        hits: int | None = None,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """
        Return injected payload and record call parameters.

        Args:
            query: Search keywords.
            hits: Maximum number of results.
            page: Page number (1-based).
            sort: Sort order.

        Returns:
            Injected JSON response.

        Raises:
            Exception: When an error was injected for testing.
        """
        self.last_query = query
        self.last_hits = hits
        self.last_page = page
        self.last_sort = sort
        if self.error is not None:
            raise self.error
        return self.payload

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Replace the response payload."""
        self.payload = payload

    def set_error(self, error: Exception | None) -> None:
        """Set or clear an injected error."""
        self.error = error
