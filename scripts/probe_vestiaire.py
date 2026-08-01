"""Probe Vestiaire Collective public search HTML structure."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from marketplace.browser_acquisition.browser_session import BrowserSession

OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

URLS = [
    "https://www.vestiairecollective.com/search/?q=Chanel%20wallet",
    "https://us.vestiairecollective.com/search/?q=Chanel%20Classic",
    "https://www.vestiairecollective.com/search/?q=Hermes%20Kelly",
]


def main() -> None:
    session = BrowserSession()
    for index, url in enumerate(URLS):
        print("===", url)
        try:
            fetch = session.fetch_html(
                url,
                wait_selector="a[href*='/product'], a[href*='/items'], article, [data-testid]",
            )
        except Exception as exc:  # noqa: BLE001
            print("FAIL", type(exc).__name__, exc)
            continue
        html = fetch.html or ""
        path = OUT / f"vestiaire_probe_{index}.html"
        path.write_text(html, encoding="utf-8")
        print("blocked", fetch.blocked_reason, "len", len(html), "wrote", path.name)
        low = html.lower()
        for token in (
            "captcha",
            "consent",
            "cookie",
            "login",
            "sign in",
            "/product",
            "/items/",
            "data-testid",
            "sold",
            "reserved",
            "€",
            "$",
            "£",
            "eur",
            "usd",
            "gbp",
            "didomi",
            "onetrust",
        ):
            if token.lower() in low or token in html:
                print("  has", token)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        productish = [h for h in hrefs if re.search(r"/(product|items|p)/", h, re.I)]
        print("  productish hrefs", len(productish))
        for sample in productish[:8]:
            print("   ", sample[:140])
        prices = re.findall(r"(?:€|£|\$|USD|EUR|GBP)\s*[\d.,]+|[\d.,]+\s*(?:€|£|\$|USD|EUR|GBP)", html[:200000])
        print("  price samples", prices[:12])


if __name__ == "__main__":
    main()
