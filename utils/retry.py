"""
Retry decorator for network and transient failures.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import MAX_RETRY

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., object])


def with_retry(func: F) -> F:
    """
    Decorate a function with exponential backoff retry logic.

    Retries on HTTP errors and connection failures up to MAX_RETRY attempts.
    """

    @retry(
        stop=stop_after_attempt(MAX_RETRY),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.HTTPError, httpx.TimeoutException, ConnectionError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
