"""Saved HTML candidate parsers."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Protocol

from bs4 import BeautifulSoup

from marketplace.acquisition_workspace.models import ParsedCandidate

CAPTCHA_MARKERS = ("captcha", "verify you are human", "access denied", "robot")


class SavedHtmlCandidateParser(Protocol):
    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        ...

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        ...


class GenericProductJsonLdParser:
    name = "json_ld"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        return "application/ld+json" in html.lower()

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        if _contains_captcha(html):
            return []
        soup = BeautifulSoup(html, "lxml")
        results: list[ParsedCandidate] = []
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for entity in _iter_entities(payload):
                parsed = _entity_to_candidate(entity, self.name)
                if parsed:
                    results.append(parsed)
        return results


class GenericOpenGraphParser:
    name = "open_graph"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        lowered = html.lower()
        return 'property="og:title"' in lowered or "og:title" in lowered

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        if _contains_captcha(html):
            return []
        soup = BeautifulSoup(html, "lxml")
        title = _meta_content(soup, "og:title")
        price_text = _meta_content(soup, "product:price:amount") or _meta_content(soup, "og:price:amount")
        currency = _meta_content(soup, "product:price:currency") or "USD"
        url = _meta_content(soup, "og:url") or source_url or ""
        image = _meta_content(soup, "og:image")
        if not title:
            return []
        price = _parse_price(price_text)
        if price is None:
            return [
                ParsedCandidate(
                    title=title,
                    brand="",
                    category="",
                    condition="",
                    purchase_price=Decimal("0"),
                    currency=currency,
                    purchase_url=url,
                    source_name="Saved HTML",
                    external_id="",
                    image_url=image,
                    raw_description="",
                    parser_strategy=self.name,
                    warnings=("missing price",),
                )
            ]
        return [
            ParsedCandidate(
                title=title,
                brand="",
                category="",
                condition="",
                purchase_price=price,
                currency=currency,
                purchase_url=url,
                source_name="Saved HTML",
                external_id="",
                image_url=image,
                raw_description="",
                parser_strategy=self.name,
            )
        ]


class FashionphileSavedHtmlParser:
    name = "fashionphile_saved_html"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        lowered = html.lower()
        return "fashionphile" in lowered or "product-card" in lowered

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        if _contains_captcha(html):
            return []
        soup = BeautifulSoup(html, "lxml")
        results: list[ParsedCandidate] = []
        for card in soup.select("article.product-card"):
            link = card.select_one("a[href]")
            title_node = card.select_one(".product-title")
            price_node = card.select_one(".price")
            condition_node = card.select_one(".condition")
            if not title_node:
                continue
            price = _parse_price(price_node.get_text(strip=True) if price_node else "")
            if price is None:
                continue
            href = link["href"] if link and link.has_attr("href") else ""
            results.append(
                ParsedCandidate(
                    title=title_node.get_text(strip=True),
                    brand="Chanel" if "chanel" in title_node.get_text(strip=True).lower() else "",
                    category="Wallet",
                    condition=condition_node.get_text(strip=True) if condition_node else "",
                    purchase_price=price,
                    currency="USD",
                    purchase_url=href,
                    source_name="Fashionphile",
                    external_id=card.get("data-product-id", ""),
                    image_url="",
                    raw_description="",
                    parser_strategy=self.name,
                )
            )
        if results:
            return results
        generic = GenericProductJsonLdParser()
        if generic.can_parse(html):
            parsed = generic.parse(html, source_url)
            for item in parsed:
                results.append(
                    ParsedCandidate(
                        title=item.title,
                        brand=item.brand or "Chanel",
                        category="Wallet",
                        condition=item.condition,
                        purchase_price=item.purchase_price,
                        currency=item.currency,
                        purchase_url=item.purchase_url,
                        source_name="Fashionphile",
                        external_id=item.external_id,
                        image_url=item.image_url,
                        raw_description=item.raw_description,
                        parser_strategy=self.name,
                    )
                )
        return results


class RebagSavedHtmlParser:
    name = "rebag_saved_html"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        lowered = html.lower()
        return "rebag" in lowered or "plp__product" in lowered or "/products/" in lowered

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        from marketplace.browser_acquisition.rebag_acquirer import parse_rebag_html

        # Soft captcha badges may appear on real Rebag pages; parse products first.
        listings = parse_rebag_html(html)
        results: list[ParsedCandidate] = []
        for item in listings:
            if not item.url:
                continue
            results.append(
                ParsedCandidate(
                    title=item.title,
                    brand=item.brand,
                    category=item.category,
                    condition=item.condition,
                    purchase_price=item.price,
                    currency=item.currency,
                    purchase_url=item.url,
                    source_name="Rebag",
                    external_id=item.external_id,
                    image_url=item.image_url,
                    raw_description="",
                    parser_strategy=self.name,
                )
            )
        return results


class RealRealSavedHtmlParser:
    name = "realreal_saved_html"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        lowered = html.lower()
        return "therealreal" in lowered or "plp-product/" in lowered or "the realreal" in lowered

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        from marketplace.browser_acquisition.realreal_acquirer import parse_realreal_html

        listings = parse_realreal_html(html)
        results: list[ParsedCandidate] = []
        for item in listings:
            if not item.url:
                continue
            results.append(
                ParsedCandidate(
                    title=item.title,
                    brand=item.brand,
                    category=item.category,
                    condition=item.condition,
                    purchase_price=item.price,
                    currency=item.currency,
                    purchase_url=item.url,
                    source_name="The RealReal",
                    external_id=item.external_id,
                    image_url=item.image_url,
                    raw_description="",
                    parser_strategy=self.name,
                )
            )
        return results


class VestiaireSavedHtmlParser:
    name = "vestiaire_saved_html"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        lowered = html.lower()
        source = (source_url or "").lower()
        return (
            "vestiairecollective" in lowered
            or "vestiaire collective" in lowered
            or "catalog__productcard__" in lowered
            or "vestiairecollective.com" in source
        )

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        from marketplace.browser_acquisition.vestiaire_acquirer import parse_vestiaire_html

        listings = parse_vestiaire_html(html)
        results: list[ParsedCandidate] = []
        for item in listings:
            if not item.url:
                continue
            results.append(
                ParsedCandidate(
                    title=item.title,
                    brand=item.brand,
                    category=item.category,
                    condition=item.condition,
                    purchase_price=item.price,
                    currency=item.currency,
                    purchase_url=item.url,
                    source_name="Vestiaire Collective",
                    external_id=item.external_id,
                    image_url=item.image_url,
                    raw_description="",
                    parser_strategy=self.name,
                )
            )
        return results


class GenericProductCardParser:
    name = "product_card"

    def can_parse(self, html: str, source_url: str | None = None) -> bool:
        return "product-card" in html.lower() or "product-card" in html

    def parse(self, html: str, source_url: str | None = None) -> list[ParsedCandidate]:
        return FashionphileSavedHtmlParser().parse(html, source_url)


DEFAULT_PARSERS: list[SavedHtmlCandidateParser] = [
    VestiaireSavedHtmlParser(),
    RealRealSavedHtmlParser(),
    RebagSavedHtmlParser(),
    GenericProductJsonLdParser(),
    GenericOpenGraphParser(),
    FashionphileSavedHtmlParser(),
    GenericProductCardParser(),
]


def parse_saved_html(html: str, *, source_url: str | None = None, filename: str = "") -> tuple[list[ParsedCandidate], str, dict]:
    if _contains_captcha(html):
        return [], "blocked", {"blocked_reason": "CAPTCHA detected in saved HTML", "filename": filename}
    for parser in DEFAULT_PARSERS:
        if parser.can_parse(html, source_url):
            parsed = parser.parse(html, source_url)
            if parsed:
                return parsed, parser.name, {
                    "parser_strategy": parser.name,
                    "rows_parsed": len(parsed),
                    "filename": filename,
                }
    return [], "none", {"parser_strategy": "none", "rows_parsed": 0, "filename": filename}


def _contains_captcha(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in CAPTCHA_MARKERS)


def _meta_content(soup: BeautifulSoup, prop: str) -> str:
    node = soup.select_one(f'meta[property="{prop}"]')
    if node and node.get("content"):
        return str(node["content"]).strip()
    return ""


def _parse_price(text: str) -> Decimal | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _iter_entities(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_entities(item)
        return
    if not isinstance(payload, dict):
        return
    entity_type = payload.get("@type")
    if entity_type in {"Product", "IndividualProduct"}:
        yield payload
    if entity_type == "ItemList":
        for item in payload.get("itemListElement", []):
            if isinstance(item, dict):
                value = item.get("item", item)
                yield from _iter_entities(value)
        return
    for value in payload.values():
        if isinstance(value, (dict, list)):
            yield from _iter_entities(value)


def _entity_to_candidate(entity: dict, strategy: str) -> ParsedCandidate | None:
    title = str(entity.get("name", "")).strip()
    if not title:
        return None
    offers = entity.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price_raw = offers.get("price", "0")
    currency = str(offers.get("priceCurrency", "USD")).upper()
    try:
        price = Decimal(str(price_raw))
    except InvalidOperation:
        price = Decimal("0")
    brand = ""
    brand_payload = entity.get("brand")
    if isinstance(brand_payload, dict):
        brand = str(brand_payload.get("name", "")).strip()
    elif isinstance(brand_payload, str):
        brand = brand_payload
    return ParsedCandidate(
        title=title,
        brand=brand,
        category="",
        condition=str(entity.get("itemCondition", "")).replace("Condition", ""),
        purchase_price=price,
        currency=currency,
        purchase_url=str(entity.get("url", "")),
        source_name="Saved HTML",
        external_id=str(entity.get("sku", "") or entity.get("productID", "")),
        image_url=str(entity.get("image", "")) if isinstance(entity.get("image"), str) else "",
        raw_description=str(entity.get("description", ""))[:500],
        parser_strategy=strategy,
        warnings=() if price > 0 else ("missing price",),
    )
