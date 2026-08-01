"""Extract Vestiaire product-card samples from probe HTML."""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "output" / "vestiaire_probe_0.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "lxml")

cards = soup.select("[class*='product-card_productCard__sGjCz'], [class*='productCard__sGjCz'], a[class*='productLink']")
print("cards", len(cards))
for card in cards[:3]:
    print("---CARD---")
    print(card.get_text(" ", strip=True)[:300])
    link = card if card.name == "a" else card.select_one("a[href*='.shtml']")
    if link:
        print("href", link.get("href"))
    print(str(card)[:800])

links = soup.select("a[href$='.shtml']")
print("shtml anchors", len(links))
for link in links[:5]:
    href = link.get("href")
    text = link.get_text(" ", strip=True)[:200]
    if "purse" in (href or "") or "bag" in (href or "") or "wallet" in text.lower():
        print("L", href)
        print("T", text)

# Parse NEXT_DATA for products
payload = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.I | re.S)
data = json.loads(payload.group(1))
blob = json.dumps(data)


def find_keys(obj, needle, path="$", hits=None, limit=30):
    if hits is None:
        hits = []
    if len(hits) >= limit:
        return hits
    if isinstance(obj, dict):
        for key, value in obj.items():
            p = f"{path}.{key}"
            if needle.lower() in str(key).lower():
                hits.append((p, type(value).__name__, str(value)[:160]))
            find_keys(value, needle, p, hits, limit)
    elif isinstance(obj, list):
        for i, value in enumerate(obj[:50]):
            find_keys(value, needle, f"{path}[{i}]", hits, limit)
    return hits


for needle in ("items", "products", "price", "currency", "condition", "brand"):
    hits = find_keys(data, needle, limit=12)
    print("NEEDLE", needle, "hits", len(hits))
    for h in hits[:8]:
        print(" ", h)

# Search for product id pattern in next data
ids = re.findall(r"68880598|69492304|productIds|hits", blob)
print("id mentions", len(ids))
# Look for array of products with path .shtml
shtml_in_json = re.findall(r"/[a-z0-9\-_/]+-\d{6,}\.shtml", blob)
print("shtml in json", len(set(shtml_in_json)))
for p in list(dict.fromkeys(shtml_in_json))[:5]:
    print(" ", p)

# Find nearby JSON objects containing one shtml
m = re.search(r"\{[^{}]{0,400}68880598[^{}]{0,800}\}", blob)
print("nearby obj", m.group(0)[:500] if m else None)
