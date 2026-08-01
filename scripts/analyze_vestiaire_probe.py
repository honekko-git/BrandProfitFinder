"""Analyze saved Vestiaire probe HTML."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "output" / "vestiaire_probe_0.html").read_text(encoding="utf-8")
print("len", len(html))
title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
print("title", title.group(1).strip()[:120] if title else None)

hrefs = re.findall(r"""href=["']([^"']+)["']""", html)
print("href count", len(hrefs))
interesting = [h for h in hrefs if any(x in h.lower() for x in ("product", "item", "search", "women", "men"))]
print("interesting", len(interesting))
for h in interesting[:30]:
    print(" ", h[:180])

# Look for next-data / json payloads
for marker in ("__NEXT_DATA__", "window.__INITIAL", "application/ld+json", "productId", "product_id", "sku"):
    print(marker, marker in html)

# Extract script with product-like JSON fragments
m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.I | re.S)
if m:
    payload = m.group(1)
    print("NEXT_DATA len", len(payload))
    (ROOT / "output" / "vestiaire_next_data.json").write_text(payload, encoding="utf-8")
    try:
        data = json.loads(payload)
        print("NEXT keys", list(data.keys())[:20])
        text = json.dumps(data)[:2000]
        print(text[:1500])
    except Exception as exc:  # noqa: BLE001
        print("json fail", exc)

# Find paths like /women-... or numeric ids
paths = sorted(set(re.findall(r"/[a-z0-9\-_/]{10,}\.shtml", html, re.I)))
print("shtml paths", len(paths))
for p in paths[:20]:
    print(" ", p[:160])

paths2 = sorted(set(re.findall(r"/product(?:s)?/[a-z0-9\-_/]+", html, re.I)))
print("product paths", len(paths2))
for p in paths2[:20]:
    print(" ", p[:160])

# data attributes
attrs = sorted(set(re.findall(r"data-([a-zA-Z0-9\-]+)=", html)))
print("data attrs sample", attrs[:50])

# price-ish near product
for match in re.finditer(r"\$\s*[\d,]+(?:\.\d+)?", html):
    start = max(0, match.start() - 120)
    end = min(len(html), match.end() + 120)
    print("PRICE CTX", html[start:end].replace("\n", " ")[:240])
    break

# class names containing product/card/listing
classes = set(re.findall(r'class="([^"]+)"', html))
hit = [c for c in classes if any(x in c.lower() for x in ("product", "card", "listing", "item", "price"))]
print("class hits", len(hit))
for c in sorted(hit)[:40]:
    print(" ", c[:140])
