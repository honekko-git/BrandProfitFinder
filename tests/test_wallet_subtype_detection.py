"""Tests for wallet subtype detection."""

from __future__ import annotations

from marketplace.browser_acquisition.product_subtype import WalletSubtype, detect_wallet_subtype, subtypes_compatible


def test_long_wallet_en_jp() -> None:
    assert detect_wallet_subtype("Chanel long wallet black caviar") == WalletSubtype.LONG_WALLET
    assert detect_wallet_subtype("シャネル 長財布 黒") == WalletSubtype.LONG_WALLET


def test_bifold_trifold_detection() -> None:
    assert detect_wallet_subtype("Chanel bifold wallet") == WalletSubtype.BIFOLD_WALLET
    assert detect_wallet_subtype("シャネル 二つ折り 財布") == WalletSubtype.BIFOLD_WALLET
    assert detect_wallet_subtype("Chanel trifold wallet") == WalletSubtype.TRIFOLD_WALLET
    assert detect_wallet_subtype("三つ折り 財布") == WalletSubtype.TRIFOLD_WALLET


def test_compact_and_woc_detection() -> None:
    assert detect_wallet_subtype("Chanel Classic Wallet Black Caviar") == WalletSubtype.COMPACT_WALLET
    assert detect_wallet_subtype("CHANEL wallet on chain black") == WalletSubtype.WALLET_ON_CHAIN
    assert detect_wallet_subtype("シャネル WOC 黒") == WalletSubtype.WALLET_ON_CHAIN


def test_accessory_subtype_detection() -> None:
    assert detect_wallet_subtype("CHANEL coin case black") == WalletSubtype.COIN_CASE
    assert detect_wallet_subtype("シャネル コインケース") == WalletSubtype.COIN_CASE
    assert detect_wallet_subtype("CHANEL card holder") == WalletSubtype.CARD_HOLDER
    assert detect_wallet_subtype("カードケース 黒") == WalletSubtype.CARD_HOLDER
    assert detect_wallet_subtype("CHANEL key case") == WalletSubtype.KEY_CASE
    assert detect_wallet_subtype("キーケース") == WalletSubtype.KEY_CASE


def test_accessory_not_compatible_with_wallet() -> None:
    assert subtypes_compatible(WalletSubtype.COMPACT_WALLET, WalletSubtype.COIN_CASE) is False
    assert subtypes_compatible(WalletSubtype.COMPACT_WALLET, WalletSubtype.CARD_HOLDER) is False
    assert subtypes_compatible(WalletSubtype.COMPACT_WALLET, WalletSubtype.KEY_CASE) is False
    assert subtypes_compatible(WalletSubtype.COMPACT_WALLET, WalletSubtype.COMPACT_WALLET) is True


def test_unknown_pairs_not_compatible() -> None:
    assert subtypes_compatible(WalletSubtype.UNKNOWN, WalletSubtype.COMPACT_WALLET) is False
    assert subtypes_compatible(WalletSubtype.COMPACT_WALLET, WalletSubtype.UNKNOWN) is False
