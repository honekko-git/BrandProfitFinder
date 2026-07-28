"""
Grailed client protocol and fake client for fixture-based data.
"""

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GrailedClientProtocol(Protocol):
    """Protocol for Grailed search clients."""

    def search_items(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int | None = None,
        filters: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """
        Search Grailed listings from a configured data source.

        Returns:
            Parsed JSON in BrandProfitFinder internal Grailed standard format.
        """
        ...


class FakeGrailedClient:
    """In-memory Grailed client for tests and demo mode."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        pages: dict[int, dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        if pages is not None:
            self._pages = {key: deepcopy(value) for key, value in pages.items()}
        elif payload is not None:
            self._pages = {1: deepcopy(payload)}
        else:
            self._pages = {1: {"marketplace": "grailed", "items": [], "total": 0, "page": 1}}
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
        self.call_count += 1
        self.last_query = query
        self.last_page = page
        self.last_page_size = page_size
        self.last_filters = deepcopy(filters) if filters is not None else None
        if self.error is not None:
            raise self.error
        empty: dict[str, object] = {
            "marketplace": "grailed",
            "items": [],
            "total": 0,
            "page": page,
        }
        return deepcopy(self._pages.get(page, empty))

    def set_payload(self, payload: dict[str, object]) -> None:
        self._pages = {1: deepcopy(payload)}

    def set_pages(self, pages: dict[int, dict[str, object]]) -> None:
        self._pages = {key: deepcopy(value) for key, value in pages.items()}

    def set_error(self, error: Exception | None) -> None:
        self.error = error
