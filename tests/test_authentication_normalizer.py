"""Tests for authentication normalizer."""

from models.authentication_info import AuthenticationStatus
from used_luxury.authentication_normalizer import AuthenticationNormalizer


def test_platform_authenticated() -> None:
    info = AuthenticationNormalizer().normalize(
        {"status": "PLATFORM_REVIEWED", "platform_authenticated": True, "provider": "Demo"}
    )
    assert info.status == AuthenticationStatus.PLATFORM_REVIEWED


def test_third_party_authenticated() -> None:
    info = AuthenticationNormalizer().normalize(
        {"third_party_authenticated": True, "provider": "Demo Auth Co"}
    )
    assert info.status == AuthenticationStatus.THIRD_PARTY_REVIEWED


def test_seller_claim_only() -> None:
    info = AuthenticationNormalizer().normalize({"seller_claimed_authentic": True})
    assert info.status == AuthenticationStatus.SELLER_CLAIM_ONLY
    assert any("seller claim" in w.lower() for w in info.warnings)


def test_unknown_status() -> None:
    info = AuthenticationNormalizer().normalize({})
    assert info.status == AuthenticationStatus.UNKNOWN


def test_concern_status() -> None:
    info = AuthenticationNormalizer().normalize({"status": "AUTHENTICITY_CONCERN"})
    assert info.status == AuthenticationStatus.AUTHENTICITY_CONCERN


def test_seller_verified_not_authenticated() -> None:
    info = AuthenticationNormalizer().normalize(
        {"seller_claimed_authentic": True, "status": "AUTHENTICATED"}
    )
    assert info.status == AuthenticationStatus.SELLER_CLAIM_ONLY


def test_certificate_preserved() -> None:
    info = AuthenticationNormalizer().normalize({"certificate_number": "CERT-123", "provider": "Lab"})
    assert info.certificate_number == "CERT-123"
    assert info.provider == "Lab"
