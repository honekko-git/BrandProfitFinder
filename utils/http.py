"""
HTTP client utilities.

Provides a reusable client for future store and marketplace integrations.
No scraping logic is implemented at this layer.
"""

import logging
from typing import Any

import httpx

from config.settings import REQUEST_TIMEOUT, USER_AGENT
from utils.retry import with_retry

logger = logging.getLogger(__name__)


def build_headers() -> dict[str, str]:
    """Build default request headers."""
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


class HttpClient:
    """HTTP client wrapper with retry support."""

    def __init__(
        self,
        timeout: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """
        Initialize the HTTP client.

        Args:
            timeout: Request timeout in seconds.
            client: Optional injected httpx.Client for testing.
        """
        self._timeout = timeout if timeout is not None else REQUEST_TIMEOUT
        self._client = client

    @with_retry
    def fetch_text(self, url: str) -> str:
        """
        Fetch a URL and return its text content.

        Args:
            url: Target URL.

        Returns:
            Response body as text.

        Raises:
            httpx.HTTPError: When the request fails after retries.
        """
        logger.debug("Fetching URL: %s", url)
        if self._client is not None:
            response = self._client.get(url)
            response.raise_for_status()
            return response.text

        with httpx.Client(
            headers=build_headers(),
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    @with_retry
    def fetch_json(self, url: str) -> Any:
        """
        Fetch a URL and return parsed JSON.

        Args:
            url: Target URL.

        Returns:
            Parsed JSON payload.
        """
        logger.debug("Fetching JSON: %s", url)
        if self._client is not None:
            response = self._client.get(url)
            response.raise_for_status()
            return response.json()

        with httpx.Client(
            headers=build_headers(),
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()


def fetch_url(url: str, timeout: int | None = None) -> str:
    """
    Fetch a URL and return its text content.

    Args:
        url: Target URL.
        timeout: Optional override for request timeout in seconds.

    Returns:
        Response body as text.
    """
    return HttpClient(timeout=timeout).fetch_text(url)


def fetch_json(url: str, timeout: int | None = None) -> Any:
    """
    Fetch a URL and return parsed JSON.

    Args:
        url: Target URL.
        timeout: Optional override for request timeout in seconds.

    Returns:
        Parsed JSON payload.
    """
    return HttpClient(timeout=timeout).fetch_json(url)
