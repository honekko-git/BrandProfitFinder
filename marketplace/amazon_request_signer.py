"""
Amazon Product Advertising API request signing (AWS Signature Version 4).

Signing is independent from HttpTransport. Secrets are never logged.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

_AMZ_ALGORITHM = "AWS4-HMAC-SHA256"
_AMZ_SERVICE = "ProductAdvertisingAPI"
_SIGNED_HEADER_NAMES = ("content-encoding", "content-type", "host", "x-amz-content-sha256", "x-amz-date", "x-amz-target")


@dataclass(frozen=True, slots=True)
class SignedAmazonRequest:
    """Signed HTTP request components ready for transport."""

    method: str
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class AmazonSignerConfig:
    """Credentials and region settings for Amazon request signing."""

    access_key: str
    secret_key: str
    region: str
    host: str
    target: str = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"


class AmazonRequestSigner:
    """Sign Amazon PA-API 5.0 requests using AWS Signature Version 4."""

    def __init__(self, config: AmazonSignerConfig) -> None:
        self.config = config

    def sign(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        content_type: str = "application/json; charset=utf-8",
        amz_date: datetime | None = None,
    ) -> SignedAmazonRequest:
        """
        Return signed headers and body for an Amazon API request.

        Args:
            method: HTTP method (POST for PA-API).
            path: Request path (e.g. /paapi5/searchitems).
            body: Raw JSON request body bytes.
            content_type: Content-Type header value.
            amz_date: Optional fixed timestamp for deterministic tests.

        Returns:
            SignedAmazonRequest with Authorization and required AWS headers.
        """
        timestamp = amz_date or datetime.now(timezone.utc)
        amz_date_str = timestamp.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = timestamp.strftime("%Y%m%d")
        host = self.config.host
        url = f"https://{host}{path}"
        payload_hash = hashlib.sha256(body).hexdigest()

        headers = {
            "content-encoding": "amz-1.0",
            "content-type": content_type,
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date_str,
            "x-amz-target": self.config.target,
        }

        canonical_headers, signed_headers = _canonical_headers(headers)
        canonical_request = "\n".join(
            [
                method.upper(),
                path,
                "",
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = f"{date_stamp}/{self.config.region}/{_AMZ_SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [
                _AMZ_ALGORITHM,
                amz_date_str,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signing_key = _derive_signing_key(self.config.secret_key, date_stamp, self.config.region, _AMZ_SERVICE)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"{_AMZ_ALGORITHM} "
            f"Credential={self.config.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        signed = dict(headers)
        signed["Authorization"] = authorization
        return SignedAmazonRequest(method=method.upper(), url=url, headers=signed, body=body)


def mask_signed_headers_for_log(headers: Mapping[str, str]) -> dict[str, str]:
    """Return headers safe for logging with credentials and signatures redacted."""
    masked: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered == "authorization":
            masked[key] = "AWS4-HMAC-SHA256 Credential=***/***/***/***, SignedHeaders=***, Signature=***"
        else:
            masked[key] = value
    return masked


def _canonical_headers(headers: Mapping[str, str]) -> tuple[str, str]:
    normalized = {key.lower(): value.strip() for key, value in headers.items()}
    lines = [f"{name}:{normalized[name]}" for name in sorted(normalized) if name in _SIGNED_HEADER_NAMES]
    canonical = "\n".join(lines) + "\n"
    signed = ";".join(name for name in sorted(normalized) if name in _SIGNED_HEADER_NAMES)
    return canonical, signed


def _derive_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    key = ("AWS4" + secret_key).encode("utf-8")
    for part in (date_stamp, region, service, "aws4_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    return key
