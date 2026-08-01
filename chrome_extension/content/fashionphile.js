/* Fashionphile search-results extraction (visible DOM only). */
(function () {
  const CARD_SELECTORS = [
    "div.fp-algolia-product-card",
    "div.card-wrapper.product-card-wrapper",
    "li.ais-Hits-item div.card",
    "[data-product-id].ais-product",
    "article.product-card",
  ];

  function detectPage() {
    const hostOk = BPF.validation.isFashionphileHostname(window.location.hostname);
    if (!hostOk) {
      return { ok: false, code: BPF.CODES.NOT_FASHIONPHILE, products: [] };
    }

    const path = window.location.pathname || "";
    const hasSearchPath = /\/search\b/i.test(path) || /[?&]q=/.test(window.location.search);
    const cards = queryCards();
    const bodyText = (document.body && document.body.innerText) || "";
    const challengeOnly =
      cards.length === 0 &&
      (/verify you are human|are you a robot|h-captcha|g-recaptcha-response|captcha challenge/i.test(
        document.documentElement.innerHTML
      ) ||
        /access denied|unusual traffic/i.test(bodyText));

    if (challengeOnly) {
      return { ok: false, code: BPF.CODES.CAPTCHA_ONLY, products: [] };
    }

    if (!cards.length) {
      if (!hasSearchPath && !/\/collections\//i.test(path) && !/\/shop\b/i.test(path)) {
        return { ok: false, code: BPF.CODES.NOT_SEARCH_RESULTS, products: [] };
      }
      return { ok: false, code: BPF.CODES.NO_PRODUCTS, products: [] };
    }

    return { ok: true, code: BPF.CODES.OK, products: [], cardCount: cards.length };
  }

  function queryCards() {
    const seen = new Set();
    const out = [];
    for (const selector of CARD_SELECTORS) {
      document.querySelectorAll(selector).forEach((node) => {
        const card = normalizeCardRoot(node);
        if (!card || seen.has(card)) return;
        seen.add(card);
        out.push(card);
      });
      if (out.length) break;
    }
    return out;
  }

  function normalizeCardRoot(node) {
    if (!node) return null;
    if (node.matches && node.matches("div.fp-algolia-product-card, article.product-card")) return node;
    return (
      node.closest("div.fp-algolia-product-card") ||
      node.closest("div.card-wrapper.product-card-wrapper") ||
      node.closest("li.ais-Hits-item") ||
      node
    );
  }

  function extractProducts() {
    const page = detectPage();
    if (!page.ok) return page;

    const rejected = [];
    const products = [];
    const dedupe = new Set();

    queryCards().forEach((card) => {
      const result = extractOne(card);
      if (!result.ok) {
        rejected.push({ reason: result.reason });
        return;
      }
      const key = result.product.url;
      if (dedupe.has(key)) {
        rejected.push({ reason: "duplicate" });
        return;
      }
      dedupe.add(key);
      products.push(result.product);
    });

    if (!products.length) {
      return {
        ok: false,
        code: BPF.CODES.EXTRACT_FAILED,
        products: [],
        rejected_count: rejected.length,
        rejection_reasons: summarizeReasons(rejected),
      };
    }

    return {
      ok: true,
      code: BPF.CODES.OK,
      products,
      rejected_count: rejected.length,
      rejection_reasons: summarizeReasons(rejected),
      source_page_url: window.location.href,
      visible_card_count: queryCards().length,
    };
  }

  function summarizeReasons(rows) {
    const counts = {};
    rows.forEach((row) => {
      counts[row.reason] = (counts[row.reason] || 0) + 1;
    });
    return counts;
  }

  function extractOne(card) {
    const text = (card.innerText || "").toLowerCase();
    if (/\bsold out\b|\bunavailable\b|\bno longer available\b/.test(text)) {
      return { ok: false, reason: "sold_or_unavailable" };
    }

    const link =
      card.querySelector("a.fp-card__link[href*='/products/']") ||
      card.querySelector("a.full-unstyled-link[href*='/products/']") ||
      card.querySelector("a[href*='/products/']");
    if (!link) return { ok: false, reason: "missing_url" };

    let url;
    try {
      url = BPF.validation.canonicalizeProductUrl(link.href);
    } catch (_err) {
      return { ok: false, reason: "invalid_url" };
    }
    if (!BPF.validation.isProductUrl(url)) return { ok: false, reason: "invalid_url" };

    const nameNode =
      card.querySelector(".fp-card__link__product-name") ||
      card.querySelector(".ais-hit--title .fp-card__link") ||
      card.querySelector(".product-title") ||
      card.querySelector("h3, h2");
    const vendorNode = card.querySelector(".fp-card__vendor, .vendor, .card__vendor");
    let title = "";
    if (nameNode) title = nameNode.textContent.replace(/\s+/g, " ").trim();
    const brand = vendorNode ? vendorNode.textContent.replace(/\s+/g, " ").trim() : "";
    if (brand && title && !title.toLowerCase().startsWith(brand.toLowerCase())) {
      title = `${brand} ${title}`.trim();
    }
    if (!title) return { ok: false, reason: "missing_title" };

    const saleNode =
      card.querySelector(".price-item--sale") ||
      card.querySelector("[data-testid='product-price']") ||
      card.querySelector(".product-price") ||
      card.querySelector(".price");
    // Prefer sale/current price; ignore compare-at / regular crossed-out nodes.
    const compareNodes = card.querySelectorAll(
      ".price-item--regular, s.price-item, .price__compare, del"
    );
    let priceText = saleNode ? saleNode.textContent : "";
    if (!priceText) {
      // Fallback: first money-like text that is not inside a compare node.
      const priceRoot = card.querySelector(".price, .fp-price-items");
      priceText = priceRoot ? priceRoot.textContent : "";
      compareNodes.forEach((node) => {
        priceText = priceText.replace(node.textContent || "", " ");
      });
    }
    const parsed = BPF.validation.parsePriceText(priceText);
    if (!parsed) return { ok: false, reason: "missing_or_invalid_price" };
    if (!parsed.currency) return { ok: false, reason: "ambiguous_currency" };

    let originalPrice = null;
    compareNodes.forEach((node) => {
      const cmp = BPF.validation.parsePriceText(node.textContent);
      if (cmp && cmp.amount > parsed.amount) originalPrice = cmp.amount;
    });

    const conditionNode = card.querySelector(".fp-condition, .condition, [data-condition]");
    let condition = "";
    if (conditionNode) {
      condition = conditionNode.textContent
        .replace(/Cond(ition)?:\s*/i, "")
        .replace(/\s+/g, " ")
        .trim();
    }

    const image =
      (card.querySelector("img.ais-hit--picture, img.fp-injected-primary-image, img") || {})
        .src || "";

    const productId =
      card.getAttribute("data-product-id") ||
      card.getAttribute("data-variant-id") ||
      card.getAttribute("data-handle") ||
      "";

    return {
      ok: true,
      product: {
        acquisition_marketplace: "Fashionphile",
        title,
        brand: brand || "",
        current_price: parsed.amount,
        currency: parsed.currency,
        formatted_price: parsed.formatted,
        original_price: originalPrice,
        url,
        image_url: image || "",
        condition: condition || "",
        product_id: String(productId || ""),
        availability: "available",
        category: "",
      },
    };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== "BPF_EXTRACT_FASHIONPHILE") return;
    try {
      if (message.action === "detect") {
        sendResponse(detectPage());
        return;
      }
      sendResponse(extractProducts());
    } catch (_err) {
      sendResponse({ ok: false, code: BPF.CODES.EXTRACT_FAILED, products: [] });
    }
  });
})();
