/* Shared message / status codes for BrandProfitFinder extension. */
(function (root) {
  const CODES = {
    OK: "OK",
    NOT_FASHIONPHILE: "NOT_FASHIONPHILE",
    NOT_SEARCH_RESULTS: "NOT_SEARCH_RESULTS",
    NO_PRODUCTS: "NO_PRODUCTS",
    CAPTCHA_ONLY: "CAPTCHA_ONLY",
    UNSUPPORTED_PAGE: "UNSUPPORTED_PAGE",
    EXTRACT_FAILED: "EXTRACT_FAILED",
  };

  const USER_MESSAGES = {
    NOT_FASHIONPHILE: "Fashionphileの検索結果ページを開いてください",
    NOT_SEARCH_RESULTS: "Fashionphileの検索結果ページを開いてください",
    NO_PRODUCTS: "商品が表示されていません",
    CAPTCHA_ONLY: "このページは現在対応していません",
    UNSUPPORTED_PAGE: "このページは現在対応していません",
    EXTRACT_FAILED: "有効な商品URLを取得できませんでした",
    SERVER_DOWN: "BrandProfitFinderが起動していません",
    CONNECT_FAILED: "BrandProfitFinderへ接続できません",
    ALL_IMPORTED: "このページの表示商品はすべて取り込み済みです。",
  };

  root.BPF = root.BPF || {};
  root.BPF.CODES = CODES;
  root.BPF.USER_MESSAGES = USER_MESSAGES;
  root.BPF.EXTENSION_VERSION = "1.0.3";
  root.BPF.LOCAL_BASE = "http://127.0.0.1:8000";
  root.BPF.CAPTURE_PATH = "/acquisition-workspace/import/browser-capture";
  root.BPF.BULK_START_PATH = "/acquisition-workspace/bulk-acquisition/start";
  root.BPF.KNOWN_URLS_PATH = "/acquisition-workspace/import/browser-capture/known-urls";
  // Must stay aligned with server MAX_CAPTURE_PRODUCTS (do not raise here alone).
  root.BPF.MAX_CAPTURE_PRODUCTS = 80;
  root.BPF.STORAGE_KEY = "bpf_fashionphile_capture_v1";
  root.BPF.USER_MESSAGES.CHALLENGE =
    "Fashionphileの確認画面を完了して、商品一覧が表示されたら続行してください。";
  root.BPF.USER_MESSAGES.NO_VISIBLE =
    "Fashionphileの商品一覧が表示されていません";
  root.BPF.USER_MESSAGES.BRAND_UNAVAILABLE = "このブランドは現在取得できません";
  root.BPF.USER_MESSAGES.IMPORT_ERROR = "取り込み中にエラーが発生しました";
  root.BPF.USER_MESSAGES.NO_VALID_PRODUCTS = "有効な商品が見つかりません";
  root.BPF.USER_MESSAGES.ALL_IMPORTED = "このページの表示商品はすべて取り込み済みです。";
})(typeof globalThis !== "undefined" ? globalThis : window);
