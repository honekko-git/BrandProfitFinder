"""
Amazon client protocol and shared search types.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AmazonClientProtocol(Protocol):
    """Protocol for Amazon product search clients."""

    def search_items(
        self,
        *,
        query: str,
        page: int = 1,
        max_results: int | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Search Amazon.co.jp product listings.

        Args:
            query: Search keywords.
            page: Page number (1-based).
            max_results: Maximum number of results to return.
            page_token: Optional pagination token.

        Returns:
            Parsed JSON response object in the internal standard format.
        """
        ...


class FakeAmazonClient:
    """In-memory Amazon client for tests and demo mode."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        """
        Initialize fake client with optional fixed payload.

        Args:
            payload: JSON response returned by search_items.
        """
        self.payload = payload or {"items": [], "total_results": 0, "next_page_token": None}
        self.last_query: str = ""
        self.last_page: int = 1
        self.last_max_results: int | None = None
        self.last_page_token: str | None = None

    def search_items(
        self,
        *,
        query: str,
        page: int = 1,
        max_results: int | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Return injected payload and record call parameters.

        Args:
            query: Search keywords.
            page: Page number (1-based).
            max_results: Maximum number of results to return.
            page_token: Optional pagination token.

        Returns:
            Injected JSON response.
        """
        self.last_query = query
        self.last_page = page
        self.last_max_results = max_results
        self.last_page_token = page_token
        return self.payload

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Replace the response payload."""
        self.payload = payload
