"""Tests for product identity normalization."""

from product_identity.normalization import (
    normalize_brand,
    normalize_code,
    normalize_gtin_digits,
    normalize_text,
    title_overlap_ratio,
    tokenize_title,
)


def test_normalize_text_none_and_blank() -> None:
    assert normalize_text(None) is None
    assert normalize_text("") is None
    assert normalize_text("  ") is None


def test_normalize_code_preserves_leading_zeroes() -> None:
    assert normalize_code("  ab-001  ") == "AB001"


def test_normalize_gtin_digits() -> None:
    assert normalize_gtin_digits("490-1234-567890") == "4901234567890"


def test_japanese_text_normalization() -> None:
    assert normalize_text("　テスト　商品　") == "テスト 商品"


def test_title_overlap_deterministic() -> None:
    left = "Demo Brand Model X"
    right = "demo brand model x special"
    assert title_overlap_ratio(left, right) == 1.0
    assert tokenize_title(left) == tokenize_title("Demo Brand Model X")
