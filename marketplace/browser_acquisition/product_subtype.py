"""Wallet subtype detection for comparable product matching."""

from __future__ import annotations

import re
from enum import StrEnum


class WalletSubtype(StrEnum):
    """Normalized wallet product subtype."""

    LONG_WALLET = "LONG_WALLET"
    BIFOLD_WALLET = "BIFOLD_WALLET"
    TRIFOLD_WALLET = "TRIFOLD_WALLET"
    COMPACT_WALLET = "COMPACT_WALLET"
    CARD_HOLDER = "CARD_HOLDER"
    COIN_CASE = "COIN_CASE"
    KEY_CASE = "KEY_CASE"
    WALLET_ON_CHAIN = "WALLET_ON_CHAIN"
    UNKNOWN = "UNKNOWN"


ACCESSORY_SUBTYPES = {
    WalletSubtype.CARD_HOLDER,
    WalletSubtype.COIN_CASE,
    WalletSubtype.KEY_CASE,
}

WALLET_SUBTYPES = {
    WalletSubtype.LONG_WALLET,
    WalletSubtype.BIFOLD_WALLET,
    WalletSubtype.TRIFOLD_WALLET,
    WalletSubtype.COMPACT_WALLET,
    WalletSubtype.WALLET_ON_CHAIN,
}

SUBTYPE_PATTERNS: tuple[tuple[WalletSubtype, tuple[str, ...]], ...] = (
    (WalletSubtype.COIN_CASE, ("coin purse", "coin case", "coincase", "コインケース", "小銭入れ", "コインパース")),
    (WalletSubtype.CARD_HOLDER, ("card holder", "card case", "cardholder", "カードケース", "カードホルダー", "名刺入れ")),
    (WalletSubtype.KEY_CASE, ("key case", "key holder", "キーケース", "パスケース")),
    (
        WalletSubtype.WALLET_ON_CHAIN,
        ("wallet on chain", "woc", "チェーンウォレット", "チェーン付", "チェーン ウォレット"),
    ),
    (WalletSubtype.TRIFOLD_WALLET, ("trifold", "tri-fold", "三つ折り", "3つ折り")),
    (WalletSubtype.BIFOLD_WALLET, ("bifold", "bi-fold", "二つ折り", "2つ折り", "２つ折り")),
    (WalletSubtype.LONG_WALLET, ("long wallet", "長財布")),
    (WalletSubtype.COMPACT_WALLET, ("compact wallet", "コンパクト財布", "classic wallet", "クラシック ウォレット", "クラシックウォレット")),
)

FOLD_WALLET_SUBTYPES = {
    WalletSubtype.BIFOLD_WALLET,
    WalletSubtype.COMPACT_WALLET,
}


def detect_wallet_subtype(title: str) -> WalletSubtype:
    """Detect wallet subtype from English or Japanese title text."""
    normalized = _normalize(title)
    for subtype, patterns in SUBTYPE_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return subtype
    if "zip around" in normalized or "ラウンドファスナー" in normalized:
        return WalletSubtype.LONG_WALLET
    if _looks_like_wallet(normalized):
        return WalletSubtype.COMPACT_WALLET
    return WalletSubtype.UNKNOWN


def subtypes_compatible(purchase_subtype: WalletSubtype, sample_subtype: WalletSubtype) -> bool:
    """Return True when purchase and sample subtypes may be compared."""
    if purchase_subtype == WalletSubtype.UNKNOWN or sample_subtype == WalletSubtype.UNKNOWN:
        return False
    if purchase_subtype in ACCESSORY_SUBTYPES or sample_subtype in ACCESSORY_SUBTYPES:
        return purchase_subtype == sample_subtype
    if purchase_subtype == sample_subtype:
        return True
    fold_pair = purchase_subtype in FOLD_WALLET_SUBTYPES and sample_subtype in FOLD_WALLET_SUBTYPES
    return fold_pair


def _normalize(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def _looks_like_wallet(text: str) -> bool:
    # Do not treat マトラッセ/matelasse alone as wallet — Classic Flap bags use it heavily.
    if any(token in text for token in ("ダブルフラップ", "フルフラップ", "クラシックフラップ", "flap bag", "ハンドバッグ", "ショルダーバッグ", "バッグ")):
        return False
    return any(token in text for token in ("wallet", "ウォレット", "財布"))
