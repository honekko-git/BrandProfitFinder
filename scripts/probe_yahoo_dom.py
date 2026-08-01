"""One-off probe for Yahoo closed search DOM structure."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserSession

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "browser_acquisition"
URLS = {
    "yahoo_live_ja.html": "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=%E3%82%B7%E3%83%A3%E3%83%8D%E3%83%AB+%E8%B2%A1%E5%B8%83",
    "yahoo_live_en.html": "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p=chanel+wallet+caviar",
}

SELECTORS = [
    "li.Product",
    ".Product",
    "script[type='application/ld+json']",
    "[data-auction-id]",
    ".SearchResults__item",
    ".Products__item",
    "li[class*='Product']",
    "div[class*='Product']",
    "a[href*='page.auctions.yahoo.co.jp']",
    "a[href*='auctions.yahoo.co.jp/jp/auction']",
    ".Product__title",
    ".Product__price",
]


def main() -> None:
    session = BrowserSession()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        fetch = session.fetch_html(url)
        path = OUT / name
        path.write_text(fetch.html, encoding="utf-8")
        soup = BeautifulSoup(fetch.html, "lxml")
        print(f"=== {name} ===")
        print("status", fetch.status_code, "blocked", fetch.blocked_reason)
        print("title", soup.title.string if soup.title else "N/A")
        print("html_len", len(fetch.html))
        for sel in SELECTORS:
            print(f"  {sel}: {len(soup.select(sel))}")
        # sample class names containing Product
        classes = set()
        for tag in soup.find_all(True, class_=True):
            for cls in tag.get("class", []):
                if "product" in cls.lower() or "item" in cls.lower():
                    classes.add(cls)
        print("sample classes:", sorted(list(classes))[:30])


if __name__ == "__main__":
    main()
