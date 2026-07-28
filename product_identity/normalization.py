"""Deterministic normalization utilities for product identity."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: object | None) -> str | None:
    """Normalize free text; return None for missing/blank."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.casefold()


def normalize_brand(value: object | None) -> str | None:
    """Normalize brand for comparison."""
    text = normalize_text(value)
    if text is None:
        return None
    text = re.sub(r"[^\w\s&]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_code(value: object | None) -> str | None:
    """
    Normalize structured codes preserving meaningful characters.

    Does not convert to int. Preserves leading zeroes after digit extraction.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", text).upper()
    normalized = re.sub(r"[\s\-_/]+", "", normalized)
    return normalized or None


def normalize_gtin_digits(value: object | None) -> str | None:
    """Extract digits for JAN/EAN/UPC/GTIN comparison."""
    code = normalize_code(value)
    if code is None:
        return None
    digits = re.sub(r"\D", "", code)
    return digits or None


def normalize_color(value: object | None) -> str | None:
    """Normalize color text without broad synonym expansion."""
    return normalize_text(value)


def normalize_size(value: object | None) -> tuple[str | None, str | None]:
    """
    Return (size_value, size_system) without cross-system conversion.

    size_system remains None when unknown.
    """
    text = normalize_text(value)
    if text is None:
        return None, None
    system_match = re.search(r"\b(us|uk|eu|jp|cm)\b", text)
    system = system_match.group(1).upper() if system_match else None
    value = re.sub(r"\b(us|uk|eu|jp|cm)\b", "", text).strip()
    value = re.sub(r"\s+", " ", value) or None
    return value, system


def tokenize_title(value: object | None) -> tuple[str, ...]:
    """Deterministic title tokens for weak evidence."""
    text = normalize_text(value)
    if text is None:
        return ()
    cleaned = re.sub(r"[^\w\s]", " ", text)
    tokens = tuple(sorted({token for token in cleaned.split() if len(token) > 1}))
    return tokens


def title_overlap_ratio(left: object | None, right: object | None) -> float:
    """Deterministic token overlap ratio; weak evidence only."""
    left_tokens = set(tokenize_title(left))
    right_tokens = set(tokenize_title(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    return len(overlap) / len(left_tokens)
