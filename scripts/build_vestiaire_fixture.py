"""Build Vestiaire Collective fixtures from live probe cards + diverse observed structures."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "browser_acquisition"
PROBE = ROOT / "output" / "vestiaire_probe_0.html"


def _card(
    *,
    product_id: str,
    href: str,
    brand: str,
    title: str,
    price_text: str,
    ships_from: str,
    tag: str = "",
) -> str:
    aria_bits = [brand, title]
    if tag:
        aria_bits.append(f"Tagged as {tag}")
    aria_bits.append(f"Price: {price_text}")
    aria_bits.append(f"Ships from  {ships_from}")
    aria = ", ".join(aria_bits)
    tag_html = f'<div class="product-card_productCard__tag__WeWh7">{tag}</div>' if tag else ""
    visible_brand = brand.upper()
    return f"""
<a aria-label="{aria}" class="product-card_productCard__sGjCz" data-cy="catalog__productCard__{product_id}"
   href="{href}" id="product_id_{product_id}">
  <div class="product-card_productCard__imageContainer__G8UbI">
    <img src="https://images.vestiairecollective.com/{product_id}.jpg" alt="" />
  </div>
  <div class="product-card_productCard__productDetails__9pEV5">
    {tag_html}
    <div>{visible_brand}</div>
    <div>{title}</div>
    <div class="product-card_productCard__text--price--regularPrice__FiEps">{price_text}</div>
    <div>{ships_from}</div>
  </div>
</a>
"""


DIVERSE_CARDS = [
    _card(
        product_id="70000001",
        href="/women-bags/handbags/louis-vuitton/brown-monogram-canvas-neverfull-mm-louis-vuitton-handbag-70000001.shtml",
        brand="Louis Vuitton",
        title="Monogram Neverfull MM tote bag",
        price_text="€980",
        ships_from="France",
    ),
    _card(
        product_id="70000002",
        href="/women-bags/handbags/hermes/orange-epsom-constance-to-go-hermes-handbag-70000002.shtml",
        brand="Hermès",
        title="Constance To Go Epsom orange gold hardware",
        price_text="£4,250",
        ships_from="United Kingdom",
    ),
    _card(
        product_id="70000003",
        href="/women-bags/shoulder-bags/gucci/beige-gg-marmont-gucci-shoulder-bag-70000003.shtml",
        brand="Gucci",
        title="GG Marmont shoulder bag beige leather",
        price_text="$1,150.00",
        ships_from="United States",
        tag="We love",
    ),
    _card(
        product_id="70000004",
        href="/women-bags/handbags/prada/black-nylon-re-edition-prada-handbag-70000004.shtml",
        brand="Prada",
        title="Re-Edition nylon black handbag",
        price_text="$720",
        ships_from="Italy",
    ),
    _card(
        product_id="70000005",
        href="/women-bags/handbags/dior/blue-cannage-lady-dior-dior-handbag-70000005.shtml",
        brand="Dior",
        title="Lady Dior Cannage medium blue",
        price_text="€2,450",
        ships_from="France",
    ),
    _card(
        product_id="70000006",
        href="/women-bags/shoulder-bags/saint-laurent/black-leather-loulou-saint-laurent-shoulder-bag-70000006.shtml",
        brand="Saint Laurent",
        title="Loulou black leather shoulder bag",
        price_text="$1,380",
        ships_from="United States",
    ),
    _card(
        product_id="70000007",
        href="/women-bags/handbags/bottega-veneta/green-intrecciato-cassette-bottega-veneta-handbag-70000007.shtml",
        brand="Bottega Veneta",
        title="Cassette Intrecciato green",
        price_text="€1,890",
        ships_from="Italy",
    ),
    _card(
        product_id="70000008",
        href="/women-bags/handbags/fendi/brown-ff-peekaboo-fendi-handbag-70000008.shtml",
        brand="Fendi",
        title="Peekaboo FF brown handbag",
        price_text="$2,100",
        ships_from="United States",
    ),
    _card(
        product_id="70000009",
        href="/women-bags/handbags/celine/tan-leather-triomphe-celine-shoulder-bag-70000009.shtml",
        brand="Celine",
        title="Triomphe shoulder bag tan leather",
        price_text="€1,650",
        ships_from="France",
    ),
    _card(
        product_id="70000010",
        href="/women-bags/backpacks/gucci/black-leather-gucci-backpack-70000010.shtml",
        brand="Gucci",
        title="Black leather backpack",
        price_text="$890",
        ships_from="Japan",
    ),
    _card(
        product_id="70000011",
        href="/women-accessories/purses-wallets-cases/chanel/black-caviar-classic-chanel-purse-70000011.shtml",
        brand="Chanel",
        title="Classic caviar card wallet black gold hardware",
        price_text="¥128,000",
        ships_from="Japan",
    ),
    _card(
        product_id="70000012",
        href="/women-bags/clutches/louis-vuitton/brown-monogram-felicie-louis-vuitton-clutch-70000012.shtml",
        brand="Louis Vuitton",
        title="Félicie Pochette monogram clutch M80481",
        price_text="$780",
        ships_from="United States",
    ),
    # Crossed-out original + active sale price
    """
<a aria-label="Chanel, Classic flap wallet, Price: $520, Ships from  United States"
   class="product-card_productCard__sGjCz" data-cy="catalog__productCard__70000013"
   href="/women-accessories/purses-wallets-cases/chanel/black-leather-classic-chanel-purse-70000013.shtml"
   id="product_id_70000013">
  <div>CHANEL</div><div>Classic flap wallet</div>
  <div class="product-card_productCard__text--price--originalPrice__X"><s>$650</s></div>
  <div class="product-card_productCard__text--price--regularPrice__FiEps">$520</div>
</a>
""",
]


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    live_cards = []
    if PROBE.exists():
        soup = BeautifulSoup(PROBE.read_text(encoding="utf-8"), "lxml")
        for node in soup.select("a[data-cy^='catalog__productCard__']")[:12]:
            live_cards.append(str(node))

    body = "\n".join(live_cards + DIVERSE_CARDS)
    search_html = f"""<!DOCTYPE html>
<html lang="en"><head><title>Vestiaire Collective search</title></head>
<body data-site="vestiairecollective">
<main>{body}</main>
</body></html>
"""
    (FIXTURES / "vestiaire_search_results.html").write_text(search_html, encoding="utf-8")

    (FIXTURES / "vestiaire_empty.html").write_text(
        """<!DOCTYPE html><html><head><title>Search</title></head>
<body data-site="vestiairecollective"><main><p>No results found for your search.</p></main></body></html>
""",
        encoding="utf-8",
    )
    (FIXTURES / "vestiaire_captcha.html").write_text(
        """<!DOCTYPE html><html><head><title>Attention Required</title></head>
<body><h1>Captcha challenge</h1><div class="cf-challenge">Please verify you are human</div></body></html>
""",
        encoding="utf-8",
    )
    (FIXTURES / "vestiaire_consent.html").write_text(
        """<!DOCTYPE html><html><head><title>Cookies</title></head>
<body data-site="vestiairecollective">
<div id="didomi-host">We use cookies. Accept all cookies to continue.</div>
</body></html>
""",
        encoding="utf-8",
    )
    (FIXTURES / "vestiaire_product_page.html").write_text(
        f"""<!DOCTYPE html><html><head><title>Product</title>
<meta property="og:title" content="Hermès Constance To Go" />
<meta property="product:price:amount" content="4250" />
<meta property="product:price:currency" content="GBP" />
</head><body data-site="vestiairecollective">
{DIVERSE_CARDS[1]}
</body></html>
""",
        encoding="utf-8",
    )
    print("wrote fixtures", FIXTURES)


if __name__ == "__main__":
    main()
