"""Unit tests for Amazon request signing."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import pytest

from marketplace.amazon_request_signer import (
    AmazonRequestSigner,
    AmazonSignerConfig,
    mask_signed_headers_for_log,
)

SECRET_KEY = "super-secret-amazon-secret-key"
ACCESS_KEY = "AKIA_TEST_ACCESS_KEY"


def _signer() -> AmazonRequestSigner:
    return AmazonRequestSigner(
        AmazonSignerConfig(
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            region="us-west-2",
            host="webservices.amazon.co.jp",
        )
    )


def test_signed_headers_generated() -> None:
    body = b'{"Keywords":"gucci"}'
    fixed_time = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)
    signed = _signer().sign(method="POST", path="/paapi5/searchitems", body=body, amz_date=fixed_time)

    assert signed.headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=")
    assert signed.headers["x-amz-date"] == "20260728T100000Z"
    assert signed.headers["x-amz-target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    assert signed.headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
    assert signed.url == "https://webservices.amazon.co.jp/paapi5/searchitems"


def test_signature_is_deterministic_for_fixed_timestamp() -> None:
    body = b'{"Keywords":"bag"}'
    fixed_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    first = _signer().sign(method="POST", path="/paapi5/searchitems", body=body, amz_date=fixed_time)
    second = _signer().sign(method="POST", path="/paapi5/searchitems", body=body, amz_date=fixed_time)
    assert first.headers["Authorization"] == second.headers["Authorization"]


def test_mask_signed_headers_for_log_redacts_authorization() -> None:
    headers = {
        "Authorization": "AWS4-HMAC-SHA256 Credential=AKIA/20260728/us-west-2/ProductAdvertisingAPI/aws4_request, Signature=abc123",
        "x-amz-date": "20260728T100000Z",
    }
    masked = mask_signed_headers_for_log(headers)
    assert ACCESS_KEY not in masked["Authorization"]
    assert "abc123" not in masked["Authorization"]
    assert masked["x-amz-date"] == "20260728T100000Z"


def test_secrets_never_logged_during_sign(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="marketplace.amazon_request_signer")
    body = b'{"Keywords":"gucci"}'
    _signer().sign(method="POST", path="/paapi5/searchitems", body=body)
    assert SECRET_KEY not in caplog.text
    assert ACCESS_KEY not in caplog.text
