"""Foundation tests for utils.retry (no real network)."""

from unittest.mock import MagicMock

import httpx
import pytest

from utils.retry import with_retry


def test_with_retry_retries_then_succeeds() -> None:
    mock = MagicMock(
        side_effect=[
            httpx.TimeoutException("timeout"),
            "ok",
        ]
    )
    wrapped = with_retry(mock)
    assert wrapped() == "ok"
    assert mock.call_count == 2


def test_with_retry_reraises_after_max_attempts(monkeypatch) -> None:
    monkeypatch.setattr("utils.retry.MAX_RETRY", 2)
    mock = MagicMock(side_effect=httpx.TimeoutException("timeout"))
    wrapped = with_retry(mock)

    with pytest.raises(httpx.TimeoutException):
        wrapped()

    assert mock.call_count == 2
