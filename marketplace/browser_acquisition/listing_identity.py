"""Deterministic luxury listing identity normalization for product matching.

Reusable before comparable matching and Yahoo! Auctions integration.
No AI / ML — rule and alias maps only.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------

BRAND_CANONICAL: dict[str, str] = {
    "louis vuitton": "LOUIS VUITTON",
    "louisvuitton": "LOUIS VUITTON",
    "lv": "LOUIS VUITTON",
    "ルイヴィトン": "LOUIS VUITTON",
    "ルイビトン": "LOUIS VUITTON",
    "ヴィトン": "LOUIS VUITTON",
    "ビトン": "LOUIS VUITTON",
    "chanel": "CHANEL",
    "シャネル": "CHANEL",
    "hermes": "HERMES",
    "hermès": "HERMES",
    "エルメス": "HERMES",
    "gucci": "GUCCI",
    "グッチ": "GUCCI",
    "prada": "PRADA",
    "プラダ": "PRADA",
    "dior": "DIOR",
    "christian dior": "DIOR",
    "ディオール": "DIOR",
    "celine": "CELINE",
    "céline": "CELINE",
    "セリーヌ": "CELINE",
    "fendi": "FENDI",
    "フェンディ": "FENDI",
    "bottega veneta": "BOTTEGA VENETA",
    "ボッテガヴェネタ": "BOTTEGA VENETA",
    "bottega": "BOTTEGA VENETA",
    "ysl": "SAINT LAURENT",
    "saint laurent": "SAINT LAURENT",
    "yves saint laurent": "SAINT LAURENT",
    "サンローラン": "SAINT LAURENT",
    "balenciaga": "BALENCIAGA",
    "バレンシアガ": "BALENCIAGA",
    "loewe": "LOEWE",
    "ロエベ": "LOEWE",
    "goyard": "GOYARD",
    "ゴヤール": "GOYARD",
    "tiffany": "TIFFANY",
    "tiffany & co": "TIFFANY",
    "tiffany and co": "TIFFANY",
    "ティファニー": "TIFFANY",
}

BRAND_TITLE_ALIASES: dict[str, tuple[str, ...]] = {
    "LOUIS VUITTON": ("louis vuitton", "lv", "ルイヴィトン", "ルイビトン", "ヴィトン", "ビトン"),
    "CHANEL": ("chanel", "シャネル"),
    "HERMES": ("hermes", "hermès", "エルメス"),
    "GUCCI": ("gucci", "グッチ"),
    "PRADA": ("prada", "プラダ"),
    "DIOR": ("dior", "christian dior", "ディオール"),
    "CELINE": ("celine", "céline", "セリーヌ"),
    "FENDI": ("fendi", "フェンディ"),
    "BOTTEGA VENETA": ("bottega veneta", "bottega", "ボッテガ"),
    "SAINT LAURENT": ("saint laurent", "ysl", "yves saint laurent", "サンローラン"),
    "BALENCIAGA": ("balenciaga", "バレンシアガ"),
    "LOEWE": ("loewe", "ロエベ"),
    "GOYARD": ("goyard", "ゴヤール"),
    "TIFFANY": ("tiffany", "tiffany & co", "ティファニー"),
}

# ---------------------------------------------------------------------------
# Model numbers (highest-priority matching key)
# ---------------------------------------------------------------------------

# LV M/N/A style, Chanel Axxxxx, Prada SPR26Z / 1BA274, generic letter+digits.
_MODEL_NUMBER_RE = re.compile(
    r"(?<![A-Z0-9])("
    r"[A-Z]{2,4}\s?-?\d{2,4}[A-Z]?"  # SPR26Z, SPR 26Z, AB1234
    r"|[A-Z]\d{5}[A-Z]?"
    r"|[A-Z]{2}\d{4,5}"
    r"|[A-Z]\d{4}[A-Z]{1,2}"
    r"|\d[A-Z]{2}\d{3}"  # 1BA274 style
    r")(?![A-Z0-9])",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SUNGLASSES", ("sunglasses", "sunglass", "eyewear", "サングラス", "眼鏡", "メガネ")),
    ("BACKPACK", ("backpack", "ruck sack", "rucksack", "バックパック", "リュック")),
    ("TOTE_BAG", ("tote bag", "tote", "トートバッグ", "トート")),
    ("SHOULDER_BAG", ("shoulder bag", "shoulder", "ショルダーバッグ", "ショルダー")),
    ("CROSSBODY", ("crossbody", "cross body", "メッセンジャー", "斜め掛け")),
    ("HANDBAG", ("handbag", "ハンドバッグ")),
    ("CLUTCH", ("clutch", "クラッチ")),
    ("ROUND_ZIP", ("round zip", "ラウンドジップ", "ラウンドファスナー", "zip around", "zip-around")),
    ("ZIP_WALLET", ("zip wallet", "zippy", "ジップウォレット", "ジッピー")),
    ("LONG_WALLET", ("long wallet", "長財布")),
    ("WALLET_ON_CHAIN", ("wallet on chain", "woc", "チェーンウォレット")),
    ("CARD_HOLDER", ("card holder", "card case", "カードケース", "カードホルダー", "名刺入れ")),
    ("COIN_CASE", ("coin case", "coin purse", "コインケース", "小銭入れ")),
    ("KEY_CASE", ("key case", "キーケース")),
    ("WALLET", ("wallet", "財布", "ウォレット", "bifold", "二つ折り", "compact wallet")),
    # Flap / matelasse bag signals: JP Classic Flap sold titles often omit バッグ.
    ("BAG", ("bag", "バッグ", "ダブルフラップ", "フルフラップ", "クラシックフラップ", "フラップバッグ")),
)

WALLET_CATEGORIES = {
    "WALLET",
    "LONG_WALLET",
    "ZIP_WALLET",
    "ROUND_ZIP",
    "WALLET_ON_CHAIN",
    "CARD_HOLDER",
    "COIN_CASE",
    "KEY_CASE",
}
BAG_CATEGORIES = {
    "BACKPACK",
    "TOTE_BAG",
    "SHOULDER_BAG",
    "CROSSBODY",
    "HANDBAG",
    "CLUTCH",
    "BAG",
}
ACCESSORY_CATEGORIES = {"CARD_HOLDER", "COIN_CASE", "KEY_CASE"}

# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------

COLOR_ALIASES: dict[str, str] = {
    "black": "BLACK",
    "noir": "BLACK",
    "nero": "BLACK",
    "schwarz": "BLACK",
    "黒": "BLACK",
    "ブラック": "BLACK",
    "white": "WHITE",
    "blanc": "WHITE",
    "bianco": "WHITE",
    "白": "WHITE",
    "ホワイト": "WHITE",
    "beige": "BEIGE",
    "ベージュ": "BEIGE",
    "navy": "NAVY",
    "ネイビー": "NAVY",
    "red": "RED",
    "rouge": "RED",
    "rosso": "RED",
    "赤": "RED",
    "レッド": "RED",
    "pink": "PINK",
    "ピンク": "PINK",
    "green": "GREEN",
    "vert": "GREEN",
    "グリーン": "GREEN",
    "緑": "GREEN",
    "blue": "BLUE",
    "bleu": "BLUE",
    "ブルー": "BLUE",
    "青": "BLUE",
    "brown": "BROWN",
    "茶色": "BROWN",
    "ブラウン": "BROWN",
    "gray": "GRAY",
    "grey": "GRAY",
    "gris": "GRAY",
    "グレー": "GRAY",
    "灰": "GRAY",
    "orange": "ORANGE",
    "オレンジ": "ORANGE",
    "yellow": "YELLOW",
    "イエロー": "YELLOW",
    "purple": "PURPLE",
    "パープル": "PURPLE",
    "bordeaux": "BORDEAUX",
    "ボルドー": "BORDEAUX",
    "ebony": "EBONY",
    "エベヌ": "EBONY",
}

# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------

MATERIAL_ALIASES: dict[str, str] = {
    "caviar": "CAVIAR",
    "caviar leather": "CAVIAR",
    "キャビア": "CAVIAR",
    "キャビアスキン": "CAVIAR",
    "カビア": "CAVIAR",
    "カビアン": "CAVIAR",
    "lambskin": "LAMBSKIN",
    "lamb": "LAMBSKIN",
    "ラムスキン": "LAMBSKIN",
    "ラム": "LAMBSKIN",
    "calfskin": "CALFSKIN",
    "calf": "CALFSKIN",
    "カーフ": "CALFSKIN",
    "カーフレザー": "CALFSKIN",
    "patent": "PATENT",
    "patent leather": "PATENT",
    "パテント": "PATENT",
    "エナメル": "PATENT",
    "epi": "EPI",
    "epi leather": "EPI",
    "エピ": "EPI",
    "damier": "DAMIER",
    "damier ebene": "DAMIER",
    "damier azur": "DAMIER",
    "ダミエ": "DAMIER",
    "monogram": "MONOGRAM",
    "monogram canvas": "MONOGRAM",
    "モノグラム": "MONOGRAM",
    "epsom": "EPSOM",
    "エプソン": "EPSOM",
    "エプソム": "EPSOM",
    "saffiano": "SAFFIANO",
    "サフィアーノ": "SAFFIANO",
    "acetate": "ACETATE",
    "アセテート": "ACETATE",
    "canvas": "CANVAS",
    "キャンバス": "CANVAS",
    "leather": "LEATHER",
    "レザー": "LEATHER",
    "革": "LEATHER",
}

# Longer aliases first for detection order
_MATERIAL_DETECT_ORDER: tuple[str, ...] = tuple(
    sorted(MATERIAL_ALIASES.keys(), key=len, reverse=True)
)

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

HARDWARE_ALIASES: dict[str, str] = {
    "gold hardware": "GOLD",
    "gold hw": "GOLD",
    "ghw": "GOLD",
    "gold": "GOLD",
    "ゴールド": "GOLD",
    "金具ゴールド": "GOLD",
    "silver hardware": "SILVER",
    "silver hw": "SILVER",
    "shw": "SILVER",
    "silver": "SILVER",
    "シルバー": "SILVER",
    "palladium": "PALLADIUM",
    "phw": "PALLADIUM",
    "パラジウム": "PALLADIUM",
    "ruthenium": "RUTHENIUM",
    "ルテニウム": "RUTHENIUM",
    "brass": "BRASS",
    "ブラッシュ": "BRASS",
}

_HARDWARE_DETECT_ORDER: tuple[str, ...] = tuple(
    sorted(HARDWARE_ALIASES.keys(), key=len, reverse=True)
)

# ---------------------------------------------------------------------------
# Condition
# ---------------------------------------------------------------------------

CONDITION_ALIASES: dict[str, str] = {
    "new with tags": "EXCELLENT",
    "nwt": "EXCELLENT",
    "brand new": "EXCELLENT",
    "新品": "EXCELLENT",
    "like new": "EXCELLENT",
    "pristine": "EXCELLENT",
    "giftable": "EXCELLENT",
    "極美品": "EXCELLENT",
    "excellent": "EXCELLENT",
    "美品": "EXCELLENT",
    "very good": "VERY_GOOD",
    "verygood": "VERY_GOOD",
    "良品": "VERY_GOOD",
    "good": "GOOD",
    "良好": "GOOD",
    "fair": "FAIR",
    "shows wear": "FAIR",
    "傷や汚れあり": "FAIR",
    "やや傷": "FAIR",
    "poor": "POOR",
    "heavily worn": "POOR",
    "heavy wear": "POOR",
    "状態悪": "POOR",
    "junk": "POOR",
    "ジャンク": "POOR",
    "unknown": "UNKNOWN",
}

_CONDITION_DETECT_ORDER: tuple[str, ...] = tuple(
    sorted(CONDITION_ALIASES.keys(), key=len, reverse=True)
)

_CONDITION_RANK = {
    "EXCELLENT": 5,
    "VERY_GOOD": 4,
    "GOOD": 3,
    "FAIR": 2,
    "POOR": 1,
    "UNKNOWN": 0,
}

# ---------------------------------------------------------------------------
# Title cleanup
# ---------------------------------------------------------------------------

TITLE_NOISE_PHRASES: tuple[str, ...] = (
    "fashionphile",
    "authenticated",
    "free shipping",
    "fast shipping",
    "sale",
    "clearance",
    "100% authentic",
    "authentic",
    "guaranteed",
    "rare",
    "must see",
    "no reserve",
    "buy now",
    "from japan",
    "ship from japan",
    "即決",
    "送料無料",
    "正規品",
    "本物",
    "美品です",
)


@dataclass(frozen=True, slots=True)
class ListingIdentity:
    """Normalized identity fields extracted from a listing."""

    brand: str
    model_numbers: tuple[str, ...]
    category: str
    color: str
    material: str
    hardware: str
    condition: str
    cleaned_title: str
    model_family_tokens: tuple[str, ...] = ()


def normalize_brand(value: str, *, title: str = "") -> str:
    """Normalize brand aliases to an uppercase canonical name."""
    raw = (value or "").strip()
    if raw:
        key = _fold(raw)
        compact = key.replace(" ", "")
        if key in BRAND_CANONICAL:
            return BRAND_CANONICAL[key]
        if compact in BRAND_CANONICAL:
            return BRAND_CANONICAL[compact]
        for alias, canonical in BRAND_CANONICAL.items():
            if alias in key:
                return canonical
    haystack = _fold(title)
    for alias, canonical in sorted(BRAND_CANONICAL.items(), key=lambda item: -len(item[0])):
        if alias and alias in haystack:
            return canonical
    return raw.upper() if raw else ""


def brand_aliases_for_match(brand: str) -> tuple[str, ...]:
    """Return lowercase aliases used to find a brand inside a title."""
    canonical = normalize_brand(brand)
    if canonical in BRAND_TITLE_ALIASES:
        return BRAND_TITLE_ALIASES[canonical]
    if canonical:
        return (canonical.lower(),)
    return ()


def extract_model_numbers(*texts: str) -> tuple[str, ...]:
    """Extract and normalize luxury model / style / reference codes."""
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        # Normalize spaced references: "SPR 26Z" → "SPR26Z" for matching.
        compact = re.sub(r"\b([A-Z]{2,4})\s+(\d{2,4}[A-Z]?)\b", r"\1\2", text.upper())
        for match in _MODEL_NUMBER_RE.finditer(compact):
            code = re.sub(r"[\s\-]", "", match.group(1).upper())
            if code in seen:
                continue
            if code.isdigit() and len(code) <= 4:
                continue
            # Skip tiny ambiguous tokens
            if len(code) < 4:
                continue
            seen.add(code)
            found.append(code)
    return tuple(found)


def normalize_model_number(value: str) -> str:
    """Normalize one model/style code."""
    if not value:
        return ""
    codes = extract_model_numbers(value)
    return codes[0] if codes else re.sub(r"[\s\-_/]+", "", value).upper()


def normalize_category(value: str = "", *, title: str = "") -> str:
    """Normalize product category / subtype from category field or title."""
    haystack = _fold(f"{value} {title}")
    for canonical, patterns in CATEGORY_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            return canonical
    return "UNKNOWN"


def categories_compatible(purchase_category: str, sample_category: str) -> bool:
    """Return True when categories may be compared."""
    if purchase_category == "UNKNOWN" or sample_category == "UNKNOWN":
        # Unknown sample with known purchase: allow soft scoring later
        return purchase_category == "UNKNOWN" or sample_category == "UNKNOWN"
    if purchase_category in ACCESSORY_CATEGORIES or sample_category in ACCESSORY_CATEGORIES:
        return purchase_category == sample_category
    purchase_wallet = purchase_category in WALLET_CATEGORIES
    sample_wallet = sample_category in WALLET_CATEGORIES
    purchase_bag = purchase_category in BAG_CATEGORIES
    sample_bag = sample_category in BAG_CATEGORIES
    if purchase_wallet and sample_bag:
        return False
    if purchase_bag and sample_wallet:
        return False
    if purchase_wallet and sample_wallet:
        return True
    if purchase_bag and sample_bag:
        return True
    return purchase_category == sample_category


def normalize_color(*texts: str) -> str:
    """Normalize color synonyms to an uppercase canonical color."""
    haystack = _fold(" ".join(t for t in texts if t))
    for alias in sorted(COLOR_ALIASES.keys(), key=len, reverse=True):
        if alias in haystack:
            return COLOR_ALIASES[alias]
    return ""


def normalize_material(*texts: str) -> str:
    """Normalize material / canvas family to an uppercase canonical label."""
    haystack = _fold(" ".join(t for t in texts if t))
    for alias in _MATERIAL_DETECT_ORDER:
        if alias in haystack:
            return MATERIAL_ALIASES[alias]
    return "UNKNOWN"


def materials_compatible(purchase_material: str, sample_material: str) -> bool:
    """Return True when materials can be compared."""
    if purchase_material in {"", "UNKNOWN"} or sample_material in {"", "UNKNOWN"}:
        return True
    if purchase_material == "LEATHER" and sample_material not in {"UNKNOWN", ""}:
        # Generic leather is weak — do not hard-block specific leathers
        return True
    if sample_material == "LEATHER" and purchase_material not in {"UNKNOWN", ""}:
        return True
    return purchase_material == sample_material


def normalize_hardware(*texts: str) -> str:
    """Normalize hardware finish synonyms."""
    haystack = _fold(" ".join(t for t in texts if t))
    for alias in _HARDWARE_DETECT_ORDER:
        if alias in haystack:
            return HARDWARE_ALIASES[alias]
    return ""


def normalize_condition(*texts: str) -> str:
    """Normalize marketplace condition wording to shared grades."""
    haystack = _fold(" ".join(t for t in texts if t))
    if not haystack.strip():
        return "UNKNOWN"
    for alias in _CONDITION_DETECT_ORDER:
        if alias in haystack:
            return CONDITION_ALIASES[alias]
    return "UNKNOWN"


def conditions_compatible(purchase_condition: str, sample_condition: str) -> bool:
    """Return True when condition grades are close enough to compare."""
    if sample_condition == "POOR":
        return False
    if purchase_condition in {"", "UNKNOWN"} or sample_condition in {"", "UNKNOWN"}:
        return True
    left = _CONDITION_RANK.get(purchase_condition, 0)
    right = _CONDITION_RANK.get(sample_condition, 0)
    if left == 0 or right == 0:
        return True
    return abs(left - right) <= 2


def cleanup_title(title: str) -> str:
    """Remove marketing noise, collapse spaces, normalize punctuation."""
    text = unicodedata.normalize("NFKC", title or "")
    text = text.replace("！", "!").replace("　", " ")
    lowered = text.lower()
    for phrase in TITLE_NOISE_PHRASES:
        lowered = lowered.replace(phrase, " ")
    # Keep letters/digits/CJK; turn other punctuation into spaces
    cleaned = re.sub(r"[^\w\s\u3040-\u30ff\u4e00-\u9fff\-]", " ", lowered, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_listing_identity(
    *,
    title: str,
    brand: str = "",
    category: str = "",
    condition: str = "",
    model_family_tokens: tuple[str, ...] = (),
) -> ListingIdentity:
    """Extract a full normalized identity from listing fields + title."""
    from marketplace.browser_acquisition.product_identity import extract_collection, extract_size_token

    cleaned = cleanup_title(title)
    combined = f"{title} {condition}".strip()
    collection = extract_collection(title)
    size = extract_size_token(title)
    tokens = list(model_family_tokens)
    if collection and collection not in tokens:
        tokens.insert(0, collection)
    if size and size not in tokens:
        tokens.append(size)
    return ListingIdentity(
        brand=normalize_brand(brand, title=title),
        model_numbers=extract_model_numbers(title, category),
        category=normalize_category(category, title=title),
        color=normalize_color(title),
        material=normalize_material(title),
        hardware=normalize_hardware(title),
        condition=normalize_condition(condition, title),
        cleaned_title=cleaned,
        model_family_tokens=tuple(tokens),
    )


def title_token_overlap(left_title: str, right_title: str, *, generic_tokens: set[str] | None = None) -> int:
    """Count overlapping meaningful tokens between cleaned titles."""
    generic = generic_tokens or set()
    left = _tokenize(cleanup_title(left_title)) - generic
    right = _tokenize(cleanup_title(right_title)) - generic
    return len(left & right)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("　", " ")
    return re.sub(r"\s+", " ", normalized).strip().lower()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\u3040-\u30ff\u4e00-\u9fff]+", text.lower()))
