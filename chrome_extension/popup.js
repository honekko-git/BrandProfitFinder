/* Popup: single-page capture + popular-brand bulk acquisition. */
(function () {
  const marketplaceEl = document.getElementById("marketplace");
  const visibleEl = document.getElementById("visible-count");
  const statusEl = document.getElementById("status");
  const captureBtn = document.getElementById("capture-btn");
  const actionsEl = document.getElementById("actions");
  const workspaceLink = document.getElementById("workspace-link");
  const batchConfirmEl = document.getElementById("batch-confirm");
  const batchConfirmBtn = document.getElementById("batch-confirm-btn");
  const batchCancelBtn = document.getElementById("batch-cancel-btn");

  const brandSearchEl = document.getElementById("brand-search");
  const brandListEl = document.getElementById("brand-list");
  const brandSelectAllBtn = document.getElementById("brand-select-all");
  const brandClearAllBtn = document.getElementById("brand-clear-all");
  const bulkStartBtn = document.getElementById("bulk-start-btn");
  const bulkActiveEl = document.getElementById("bulk-active");
  const bulkProgressEl = document.getElementById("bulk-progress");
  const fxPanelEl = document.getElementById("fx-panel");
  const bulkSummaryEl = document.getElementById("bulk-summary");
  const budgetPresetEl = document.getElementById("budget-preset");
  const budgetCustomEl = document.getElementById("budget-custom");
  const bulkImportBtn = document.getElementById("bulk-import-btn");
  const bulkNextBtn = document.getElementById("bulk-next-btn");
  const bulkRetryBtn = document.getElementById("bulk-retry-btn");
  const bulkSkipBtn = document.getElementById("bulk-skip-btn");
  const bulkPauseBtn = document.getElementById("bulk-pause-btn");
  const bulkResumeBtn = document.getElementById("bulk-resume-btn");
  const bulkEndBtn = document.getElementById("bulk-end-btn");
  const bulkWorkspaceLink = document.getElementById("bulk-workspace-link");

  const MAX_CAPTURE = BPF.MAX_CAPTURE_PRODUCTS || 80;
  const STORAGE_KEY = BPF.STORAGE_KEY || "bpf_fashionphile_capture_v1";
  const bulkApi = BPF.bulkSession;
  const brandApi = BPF.popularBrands;

  let pageContext = null;
  let catalog = [];
  let selectedSet = new Set();
  let bulkSession = null;

  function setStatus(text, kind) {
    statusEl.textContent = text;
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  function hideBatchConfirm() {
    batchConfirmEl.classList.add("hidden");
  }

  function userMessage(code, fallback) {
    return BPF.USER_MESSAGES[code] || fallback || "このページは現在対応していません";
  }

  function captureHeaders() {
    return {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-BrandProfitFinder-Capture": "1",
    };
  }

  async function activeTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs && tabs[0];
  }

  async function ensureContentScript(tabId) {
    try {
      await chrome.tabs.sendMessage(tabId, { type: "BPF_EXTRACT_FASHIONPHILE", action: "detect" });
      return true;
    } catch (_err) {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["shared/messages.js", "shared/validation.js", "content/fashionphile.js"],
      });
      return true;
    }
  }

  function pageStorageKey(pageUrl) {
    try {
      const u = new URL(pageUrl);
      return u.origin + u.pathname + u.search;
    } catch (_err) {
      return String(pageUrl || "");
    }
  }

  async function loadLocalState(pageUrl) {
    try {
      const stored = await chrome.storage.local.get([STORAGE_KEY]);
      const bag = stored[STORAGE_KEY] || {};
      return bag[pageStorageKey(pageUrl)] || null;
    } catch (_err) {
      return null;
    }
  }

  async function saveLocalState(pageUrl, patch) {
    try {
      const stored = await chrome.storage.local.get([STORAGE_KEY]);
      const bag = stored[STORAGE_KEY] || {};
      const key = pageStorageKey(pageUrl);
      bag[key] = Object.assign({}, bag[key] || {}, patch, {
        page_url: pageUrl,
        updated_at: new Date().toISOString(),
      });
      await chrome.storage.local.set({ [STORAGE_KEY]: bag });
    } catch (_err) {
      // Storage is advisory; backend identity wins.
    }
  }

  function setCaptureButton(remaining) {
    if (remaining > 0) {
      captureBtn.textContent = `残り${remaining}件を取り込む`;
    } else {
      captureBtn.textContent = "現在の検索結果を一括取込";
    }
  }

  function showWorkspace(workspaceUrl) {
    if (!workspaceUrl) {
      actionsEl.classList.add("hidden");
      return;
    }
    workspaceLink.href = BPF.LOCAL_BASE + workspaceUrl;
    workspaceLink.textContent = "ワークスペースを開く";
    actionsEl.classList.remove("hidden");
  }

  function formatCaptureStatus(body, detectedCount) {
    if (body.user_message) return body.user_message;
    const already = body.already_imported_count || 0;
    const imported =
      body.imported_this_run != null ? body.imported_this_run : body.imported_count || 0;
    const remaining = body.remaining_count != null ? body.remaining_count : 0;
    if (remaining > 0) {
      return [
        `${detectedCount}件の商品を検出しました。`,
        `${imported}件を取り込みました。`,
        `残り${remaining}件です。`,
      ].join("\n");
    }
    if (imported > 0 && already > 0) {
      return [
        `${detectedCount}件の商品を検出しました。`,
        `追加で${imported}件を取り込みました。`,
        "すべて取り込み済みです。",
      ].join("\n");
    }
    if (imported === 0 && (already > 0 || remaining === 0)) {
      return userMessage("ALL_IMPORTED");
    }
    return `${imported}件を取り込みました`;
  }

  async function fetchKnownUrls(urls, sourcePageUrl, extra) {
    const payload = Object.assign(
      {
        source_marketplace: "Fashionphile",
        source_page_url: sourcePageUrl,
        urls: urls,
      },
      extra || {}
    );
    const response = await fetch(BPF.LOCAL_BASE + BPF.KNOWN_URLS_PATH, {
      method: "POST",
      headers: captureHeaders(),
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok || !body || body.ok === false) {
      const err = new Error((body && body.user_message) || "known-urls failed");
      err.body = body;
      throw err;
    }
    return body;
  }

  async function postCapture(payload) {
    let response;
    try {
      response = await fetch(BPF.LOCAL_BASE + BPF.CAPTURE_PATH, {
        method: "POST",
        headers: captureHeaders(),
        body: JSON.stringify(payload),
      });
    } catch (_err) {
      return { ok: false, user_message: userMessage("SERVER_DOWN") };
    }
    let body = null;
    try {
      body = await response.json();
    } catch (_err) {
      return { ok: false, user_message: userMessage("CONNECT_FAILED") };
    }
    if (!response.ok || !body || body.ok === false) {
      return {
        ok: false,
        user_message: (body && body.user_message) || userMessage("CONNECT_FAILED"),
      };
    }
    return body;
  }

  async function extractFromTab(tab) {
    await ensureContentScript(tab.id);
    const detection = await chrome.tabs.sendMessage(tab.id, {
      type: "BPF_EXTRACT_FASHIONPHILE",
      action: "detect",
    });
    if (!detection || !detection.ok) {
      if (detection && detection.code === "CAPTCHA_ONLY") {
        return { ok: false, code: "CHALLENGE", message: userMessage("CHALLENGE") };
      }
      return {
        ok: false,
        code: detection && detection.code,
        message: userMessage(detection && detection.code, userMessage("NO_VISIBLE")),
      };
    }
    const extraction = await chrome.tabs.sendMessage(tab.id, {
      type: "BPF_EXTRACT_FASHIONPHILE",
      action: "extract",
    });
    if (!extraction || !extraction.ok) {
      return {
        ok: false,
        code: extraction && extraction.code,
        message: userMessage(
          extraction && extraction.code,
          userMessage("NO_VALID_PRODUCTS")
        ),
      };
    }
    return { ok: true, extraction: extraction, detection: detection };
  }

  async function importVisibleProducts(options) {
    const opts = options || {};
    const tab = opts.tab || (await activeTab());
    if (!tab || !tab.id) {
      return { ok: false, user_message: userMessage("NOT_FASHIONPHILE") };
    }
    let extracted;
    try {
      extracted = await extractFromTab(tab);
    } catch (_err) {
      return { ok: false, user_message: userMessage("EXTRACT_FAILED") };
    }
    if (!extracted.ok) {
      return { ok: false, user_message: extracted.message || userMessage("NO_VISIBLE") };
    }
    const extraction = extracted.extraction;
    const allProducts = Array.isArray(extraction.products) ? extraction.products : [];
    const detectedCount = allProducts.length;
    if (!detectedCount) {
      return { ok: false, user_message: userMessage("NO_VALID_PRODUCTS") };
    }

    let knownSet = new Set();
    let batchId = opts.workspace_batch_id || "";
    try {
      const known = await fetchKnownUrls(
        allProducts.map((p) => p.url).filter(Boolean),
        extraction.source_page_url || tab.url,
        {
          bulk_session_id: opts.bulk_session_id || "",
        }
      );
      knownSet = new Set(known.known_urls || []);
      if (!batchId) batchId = known.continuation_batch_id || "";
    } catch (_err) {
      return { ok: false, user_message: userMessage("CONNECT_FAILED") };
    }

    const unimported = allProducts.filter((p) => {
      if (!p.url) return false;
      try {
        const key = BPF.validation.canonicalizeProductUrl(p.url);
        return !knownSet.has(key);
      } catch (_err) {
        return !knownSet.has(p.url);
      }
    });
    const alreadyImported = detectedCount - unimported.length;
    if (!unimported.length) {
      await saveLocalState(tab.url, {
        detected: detectedCount,
        remaining: 0,
        already_imported: detectedCount,
        batch_id: batchId,
      });
      return {
        ok: true,
        detected_count: detectedCount,
        imported_this_run: 0,
        already_imported_count: alreadyImported || detectedCount,
        remaining_count: 0,
        batch_id: batchId,
        workspace_url: batchId
          ? "/acquisition-workspace?batch_id=" + batchId
          : "/acquisition-workspace",
        user_message: userMessage("ALL_IMPORTED"),
        source_page_url: extraction.source_page_url || tab.url,
      };
    }

    const tranche = unimported.slice(0, MAX_CAPTURE);
    const body = await postCapture({
      source_marketplace: "Fashionphile",
      source_page_url: extraction.source_page_url || tab.url,
      captured_at: new Date().toISOString(),
      extension_version: BPF.EXTENSION_VERSION,
      detected_count: detectedCount,
      workspace_batch_id: batchId || "",
      bulk_session_id: opts.bulk_session_id || "",
      canonical_brand: opts.canonical_brand || "",
      fx_snapshot_id: opts.fx_snapshot_id || "",
      budget_limit_jpy:
        opts.budget_limit_jpy === undefined ? null : opts.budget_limit_jpy,
      budget_preset: opts.budget_preset || "",
      run_profit: opts.run_profit !== false && !opts.bulk_session_id,
      visible_urls: allProducts.map((p) => p.url).filter(Boolean),
      products: tranche,
    });
    if (!body.ok) {
      return body;
    }
    const remaining =
      body.remaining_count != null
        ? body.remaining_count
        : Math.max(
            0,
            detectedCount - (alreadyImported + (body.imported_this_run || body.imported_count || 0))
          );
    await saveLocalState(tab.url, {
      detected: detectedCount,
      remaining: remaining,
      already_imported: detectedCount - remaining,
      batch_id: body.batch_id || batchId || "",
      last_imported_urls: body.imported_urls || [],
    });
    return Object.assign({}, body, {
      remaining_count: remaining,
      source_page_url: extraction.source_page_url || tab.url,
    });
  }

  async function refreshDetection() {
    captureBtn.disabled = true;
    actionsEl.classList.add("hidden");
    hideBatchConfirm();
    pageContext = null;
    setStatus("ページを確認しています…");
    const tab = await activeTab();
    if (!tab || !tab.id || !tab.url) {
      marketplaceEl.textContent = "—";
      visibleEl.textContent = "0";
      setStatus(userMessage("NOT_FASHIONPHILE"), "err");
      setCaptureButton(0);
      return;
    }
    let host = "";
    try {
      host = new URL(tab.url).hostname;
    } catch (_err) {
      setStatus(userMessage("UNSUPPORTED_PAGE"), "err");
      return;
    }
    if (!BPF.validation.isFashionphileHostname(host)) {
      marketplaceEl.textContent = "未対応";
      visibleEl.textContent = "0";
      setStatus(userMessage("NOT_FASHIONPHILE"), "err");
      setCaptureButton(0);
      return;
    }
    marketplaceEl.textContent = "Fashionphile";
    try {
      const extracted = await extractFromTab(tab);
      if (!extracted.ok) {
        visibleEl.textContent = "0";
        setStatus(extracted.message || userMessage("NO_VISIBLE"), "err");
        setCaptureButton(0);
        return;
      }
      const products = extracted.extraction.products || [];
      visibleEl.textContent = String(products.length || extracted.detection.cardCount || 0);
      let remainingHint = 0;
      let alreadyHint = 0;
      try {
        const urls = products.map((p) => p.url).filter(Boolean);
        if (urls.length) {
          const known = await fetchKnownUrls(urls, tab.url, {
            bulk_session_id: bulkSession ? bulkSession.session_id : "",
          });
          const knownSet = new Set(known.known_urls || []);
          alreadyHint = knownSet.size;
          remainingHint = products.filter((p) => p.url && !knownSet.has(p.url)).length;
          pageContext = {
            tabId: tab.id,
            pageUrl: tab.url,
            detected: products.length,
            remaining: remainingHint,
            already: alreadyHint,
            batchId: known.continuation_batch_id || "",
          };
        }
      } catch (_knownErr) {
        const local = await loadLocalState(tab.url);
        if (local && typeof local.remaining === "number") {
          remainingHint = local.remaining;
          alreadyHint = local.already_imported || 0;
        }
      }
      setCaptureButton(remainingHint);
      if (remainingHint === 0 && alreadyHint > 0) {
        setStatus(userMessage("ALL_IMPORTED"), "ok");
        if (pageContext && pageContext.batchId) {
          showWorkspace("/acquisition-workspace?batch_id=" + pageContext.batchId);
        }
      } else if (remainingHint > 0 && alreadyHint > 0) {
        setStatus(
          [
            `${pageContext ? pageContext.detected : products.length}件の商品を検出しました。`,
            `${alreadyHint}件は取り込み済みです。`,
            `残り${remainingHint}件です。`,
          ].join("\n"),
          "info"
        );
      } else {
        setStatus("取込可能な検索結果が表示されています。", "ok");
      }
      captureBtn.disabled = false;
    } catch (_err) {
      setStatus(userMessage("UNSUPPORTED_PAGE"), "err");
      setCaptureButton(0);
    }
  }

  async function captureSingle() {
    captureBtn.disabled = true;
    actionsEl.classList.add("hidden");
    hideBatchConfirm();
    setStatus("商品を抽出しています…");
    const body = await importVisibleProducts({ run_profit: true });
    if (!body.ok) {
      setStatus(body.user_message || userMessage("CONNECT_FAILED"), "err");
      captureBtn.disabled = false;
      return;
    }
    setStatus(formatCaptureStatus(body, body.detected_count || 0), "ok");
    setCaptureButton(body.remaining_count || 0);
    if (body.workspace_url) showWorkspace(body.workspace_url);
    captureBtn.disabled = false;
  }

  function renderBrandList() {
    const filtered = brandApi.filterPopularBrands(catalog, brandSearchEl.value || "");
    brandListEl.innerHTML = "";
    filtered.forEach((brand) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = brand.canonical_brand;
      input.checked = selectedSet.has(brand.canonical_brand);
      input.addEventListener("change", () => {
        if (input.checked) selectedSet.add(brand.canonical_brand);
        else selectedSet.delete(brand.canonical_brand);
        updateBulkSummary();
      });
      const span = document.createElement("span");
      span.textContent = brand.display_name;
      label.appendChild(input);
      label.appendChild(span);
      brandListEl.appendChild(label);
    });
  }

  function formatFxPanel(session) {
    if (!fxPanelEl) return;
    const fx = (session && session.fx_summary) || {};
    if (!fx.snapshot_id) {
      fxPanelEl.textContent = "";
      return;
    }
    const rates = fx.rates || {};
    const freshness =
      fx.freshness_status === "FRESH"
        ? "最新"
        : fx.freshness_status === "STALE"
          ? "保存レート・要注意"
          : fx.freshness_status === "MANUAL"
            ? "手動設定"
            : fx.freshness_status || "—";
    const limit =
      session.budget_limit_jpy == null
        ? "制限なし"
        : Number(session.budget_limit_jpy).toLocaleString("ja-JP") + "円";
    const age =
      fx.stored_rate_age_seconds != null
        ? Math.round(Number(fx.stored_rate_age_seconds) / 3600) + "時間前"
        : "";
    const lines = [
      "仕入れ価格上限: " + limit,
      "判定: 商品本体の円換算価格",
      "",
      "使用為替:",
      "USD/JPY " + (rates.USD_TO_JPY || "—"),
      "EUR/JPY " + (rates.EUR_TO_JPY || "—"),
      "GBP/JPY " + (rates.GBP_TO_JPY || "—"),
      "取得時刻 " + (fx.retrieved_at || "—"),
      "状態 " + freshness + (age && fx.freshness_status === "STALE" ? " / Age " + age : ""),
      "Source: " + (fx.source_name || "—"),
      "Snapshot: " + fx.snapshot_id,
    ];
    if (fx.user_message) lines.push(fx.user_message);
    if (fx.fallback_used) lines.push("フォールバック使用中");
    fxPanelEl.textContent = lines.join("\n");
  }

  function updateBulkSummary() {
    if (!bulkSummaryEl) return;
    const ordered = brandApi.resolveSelectedBrands(catalog, Array.from(selectedSet));
    if (!ordered.length) {
      bulkSummaryEl.classList.add("hidden");
      return;
    }
    const preset = budgetPresetEl ? budgetPresetEl.value : "none";
    let limitLabel = "制限なし";
    if (preset === "custom") {
      const raw = (budgetCustomEl && budgetCustomEl.value) || "";
      limitLabel = raw ? raw.replace(/,/g, "") + "円以下（自由入力）" : "自由入力（未入力）";
    } else if (preset !== "none") {
      const opt = budgetPresetEl.options[budgetPresetEl.selectedIndex];
      limitLabel = opt ? opt.textContent : preset;
    }
    bulkSummaryEl.classList.remove("hidden");
    bulkSummaryEl.textContent = [
      "選択ブランド:",
      ordered.map((b) => b.display_name).join("、"),
      "",
      "仕入れ価格上限:",
      limitLabel,
      "",
      "使用予定為替:",
      "一括取得開始時に最新レートを取得します",
    ].join("\n");
  }

  function renderBulkProgress() {
    if (!bulkSession || bulkSession.status === "ended") {
      bulkActiveEl.classList.add("hidden");
      return;
    }
    bulkActiveEl.classList.remove("hidden");
    formatFxPanel(bulkSession);
    const completed = bulkApi.completedCount(bulkSession);
    const total = bulkSession.brand_order.length;
    const lines = [
      `完了ブランド: ${completed} / ${total}`,
      bulkSession.current_brand
        ? `現在: ${bulkSession.brands[bulkSession.current_brand].display_name}`
        : "現在: —",
      "",
      "ブランド別:",
    ];
    let totalDetected = 0;
    let totalWithin = 0;
    let totalOver = 0;
    let totalExcluded = 0;
    bulkSession.brand_order.forEach((name) => {
      const item = bulkSession.brands[name];
      totalDetected += item.detected_count || 0;
      totalWithin += item.within_budget_count || 0;
      totalOver += item.over_budget_count || 0;
      totalExcluded +=
        (item.currency_unknown_count || 0) + (item.fx_unavailable_count || 0);
      let state = "未開始";
      if (item.status === "visible_complete") state = "完了（表示分）";
      else if (item.status === "skipped") state = "スキップ";
      else if (item.status === "failed") state = "失敗: " + (item.error_message || "");
      else if (item.status === "importing" || item.status === "active") {
        if (item.detected_count) {
          state =
            `表示商品: ${item.detected_count}件\n` +
            `価格上限内: ${item.within_budget_count || 0}件\n` +
            `価格上限超過: ${item.over_budget_count || 0}件\n` +
            `通貨不明: ${item.currency_unknown_count || 0}件\n` +
            `為替利用不可: ${item.fx_unavailable_count || 0}件\n` +
            `取り込み済: ${item.imported_count || 0}件\n` +
            `残り: ${item.remaining_count || 0}件`;
        } else state = "進行中";
      }
      lines.push(item.display_name);
      lines.push(state);
      lines.push("");
    });
    lines.push("セッション合計:");
    lines.push(`総検出: ${totalDetected}件`);
    lines.push(`上限内: ${totalWithin}件`);
    lines.push(`上限超過: ${totalOver}件`);
    lines.push(`除外: ${totalExcluded}件`);
    if (bulkSession.user_message) lines.push(bulkSession.user_message);
    bulkProgressEl.textContent = lines.join("\n");

    const current = bulkSession.brands[bulkSession.current_brand];
    const remaining = current ? current.remaining_count : 0;
    const visibleComplete = current && current.status === "visible_complete";
    const failed = bulkSession.status === "failed";
    const paused = bulkSession.status === "paused";
    const complete = bulkSession.status === "complete";

    bulkImportBtn.hidden = complete || paused || failed || visibleComplete;
    bulkImportBtn.textContent =
      remaining > 0 ? `残り${remaining}件を取り込む` : "現在のブランドを取り込む";
    bulkNextBtn.hidden = !(visibleComplete && !complete);
    bulkRetryBtn.hidden = !failed;
    bulkSkipBtn.hidden = !(failed || (current && current.status === "active"));
    bulkPauseBtn.hidden = complete || paused || failed;
    bulkResumeBtn.hidden = !paused;
    bulkEndBtn.hidden = complete;
    if (bulkSession.workspace_batch_id) {
      bulkWorkspaceLink.href =
        BPF.LOCAL_BASE +
        "/acquisition-workspace?batch_id=" +
        encodeURIComponent(bulkSession.workspace_batch_id);
      bulkWorkspaceLink.classList.remove("hidden");
    } else {
      bulkWorkspaceLink.classList.add("hidden");
    }
    if (complete) {
      bulkWorkspaceLink.classList.remove("hidden");
      bulkImportBtn.hidden = true;
      bulkNextBtn.hidden = true;
    }
  }

  async function persistBulk() {
    if (!bulkSession) return;
    await bulkApi.saveSession(bulkSession);
    renderBulkProgress();
  }

  async function openCurrentBrandTab() {
    const url = bulkApi.currentSearchUrl(bulkSession);
    if (!url) {
      bulkSession = bulkApi.markFailed(bulkSession, userMessage("BRAND_UNAVAILABLE"));
      await persistBulk();
      return null;
    }
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs[0];
    if (tab && tab.id) {
      await chrome.tabs.update(tab.id, { url: url, active: true });
      return tab.id;
    }
    const created = await chrome.tabs.create({ url: url, active: true });
    return created.id;
  }

  async function startBulk() {
    const ordered = brandApi.resolveSelectedBrands(catalog, Array.from(selectedSet));
    if (!ordered.length) {
      setStatus("ブランドを選択してください", "err");
      return;
    }
    const preset = budgetPresetEl ? budgetPresetEl.value : "none";
    const custom = budgetCustomEl ? budgetCustomEl.value : "";
    if (preset === "custom") {
      const cleaned = String(custom || "").replace(/,/g, "").trim();
      if (!cleaned || !/^\d+$/.test(cleaned) || Number(cleaned) <= 0) {
        setStatus("自由入力の仕入れ上限は1以上の整数円で入力してください", "err");
        return;
      }
    }
    bulkStartBtn.disabled = true;
    setStatus("最新為替を取得しています…", "info");
    let body;
    try {
      const res = await fetch(BPF.LOCAL_BASE + BPF.BULK_START_PATH, {
        method: "POST",
        headers: captureHeaders(),
        body: JSON.stringify({
          selected_brands: ordered.map((b) => b.canonical_brand),
          budget_preset: preset,
          budget_custom_jpy: custom,
        }),
      });
      body = await res.json();
    } catch (_err) {
      bulkStartBtn.disabled = false;
      setStatus(userMessage("CONNECT_FAILED"), "err");
      return;
    }
    bulkStartBtn.disabled = false;
    if (!body.ok) {
      setStatus(body.user_message || "為替レートを取得できません。", "err");
      return;
    }
    const serverSession = body.session || {};
    bulkSession = bulkApi.startSession(ordered, {
      session_id: serverSession.session_id,
      budget_limit_jpy: body.budget_limit_jpy,
      budget_preset: body.budget_preset || preset,
      fx_snapshot_id: (body.fx_snapshot && body.fx_snapshot.snapshot_id) || "",
      fx_summary: body.fx_snapshot || {},
    });
    await persistBulk();
    setStatus(body.user_message || bulkSession.user_message, "ok");
    await openCurrentBrandTab();
  }

  async function importCurrentBrand() {
    if (!bulkSession || bulkSession.status !== "active") return;
    bulkImportBtn.disabled = true;
    setStatus("現在のブランドを取り込んでいます…", "info");
    const current = bulkSession.brands[bulkSession.current_brand];
    const body = await importVisibleProducts({
      bulk_session_id: bulkSession.session_id,
      canonical_brand: current.canonical_brand,
      workspace_batch_id: bulkSession.workspace_batch_id || "",
      fx_snapshot_id: bulkSession.fx_snapshot_id || "",
      budget_limit_jpy: bulkSession.budget_limit_jpy,
      budget_preset: bulkSession.budget_preset || "",
      run_profit: false,
    });
    if (!body.ok) {
      bulkSession = bulkApi.markFailed(
        bulkSession,
        body.user_message || userMessage("IMPORT_ERROR")
      );
      await persistBulk();
      setStatus(bulkSession.user_message, "err");
      bulkImportBtn.disabled = false;
      return;
    }
    bulkSession = bulkApi.applyImportResult(bulkSession, {
      detected_count: body.detected_count || 0,
      imported_this_run: body.imported_this_run || body.imported_count || 0,
      already_imported_count: body.already_imported_count || 0,
      remaining_count: body.remaining_count || 0,
      workspace_batch_id: body.batch_id || "",
      source_page_url: body.source_page_url || "",
      within_budget_count: body.within_budget_count || 0,
      over_budget_count: body.over_budget_count || 0,
      currency_unknown_count: body.currency_unknown_count || 0,
      fx_unavailable_count: body.fx_unavailable_count || 0,
    });
    await persistBulk();
    setStatus(formatCaptureStatus(body, body.detected_count || 0), "ok");
    if (body.workspace_url) showWorkspace(body.workspace_url);
    bulkImportBtn.disabled = false;
  }

  async function goNextBrand() {
    if (!bulkSession) return;
    bulkSession = bulkApi.advanceNext(bulkSession);
    await persistBulk();
    if (bulkSession.status === "complete") {
      setStatus(bulkSession.user_message, "ok");
      return;
    }
    setStatus(bulkSession.user_message, "info");
    await openCurrentBrandTab();
  }

  captureBtn.addEventListener("click", () => {
    captureSingle().catch(() => setStatus(userMessage("CONNECT_FAILED"), "err"));
  });
  batchConfirmBtn.addEventListener("click", () => {
    hideBatchConfirm();
    captureSingle().catch(() => setStatus(userMessage("CONNECT_FAILED"), "err"));
  });
  batchCancelBtn.addEventListener("click", () => {
    hideBatchConfirm();
    setStatus("取込をキャンセルしました。", "info");
    captureBtn.disabled = false;
  });

  brandSearchEl.addEventListener("input", () => {
    renderBrandList();
    updateBulkSummary();
  });
  brandSelectAllBtn.addEventListener("click", () => {
    catalog.forEach((item) => selectedSet.add(item.canonical_brand));
    renderBrandList();
    updateBulkSummary();
  });
  brandClearAllBtn.addEventListener("click", () => {
    selectedSet.clear();
    renderBrandList();
    updateBulkSummary();
  });
  if (budgetPresetEl) {
    budgetPresetEl.addEventListener("change", () => {
      if (budgetCustomEl) {
        if (budgetPresetEl.value === "custom") budgetCustomEl.classList.remove("hidden");
        else budgetCustomEl.classList.add("hidden");
      }
      updateBulkSummary();
    });
  }
  if (budgetCustomEl) {
    budgetCustomEl.addEventListener("input", () => updateBulkSummary());
  }
  bulkStartBtn.addEventListener("click", () => {
    startBulk().catch(() => setStatus(userMessage("CONNECT_FAILED"), "err"));
  });
  bulkImportBtn.addEventListener("click", () => {
    importCurrentBrand().catch(() => setStatus(userMessage("IMPORT_ERROR"), "err"));
  });
  bulkNextBtn.addEventListener("click", () => {
    goNextBrand().catch(() => setStatus(userMessage("CONNECT_FAILED"), "err"));
  });
  bulkRetryBtn.addEventListener("click", async () => {
    bulkSession = bulkApi.retryFailed(bulkSession);
    await persistBulk();
    await openCurrentBrandTab();
  });
  bulkSkipBtn.addEventListener("click", async () => {
    bulkSession = bulkApi.skipCurrent(bulkSession);
    await persistBulk();
    if (bulkSession.status === "complete") {
      setStatus(bulkSession.user_message, "ok");
      return;
    }
    await openCurrentBrandTab();
  });
  bulkPauseBtn.addEventListener("click", async () => {
    bulkSession = bulkApi.pauseSession(bulkSession);
    await persistBulk();
  });
  bulkResumeBtn.addEventListener("click", async () => {
    bulkSession = bulkApi.resumeSession(bulkSession);
    await persistBulk();
    await openCurrentBrandTab();
  });
  bulkEndBtn.addEventListener("click", async () => {
    bulkSession = bulkApi.endSession(bulkSession);
    await persistBulk();
    await bulkApi.clearSession();
    bulkSession = null;
    bulkActiveEl.classList.add("hidden");
    setStatus("一括取得を終了しました。", "info");
  });

  async function boot() {
    try {
      catalog = await brandApi.loadPopularBrands();
      renderBrandList();
    } catch (_err) {
      brandListEl.textContent = "ブランド一覧を読み込めませんでした";
    }
    bulkSession = await bulkApi.loadSession();
    if (
      bulkSession &&
      (bulkSession.status === "active" ||
        bulkSession.status === "paused" ||
        bulkSession.status === "failed" ||
        bulkSession.status === "complete")
    ) {
      renderBulkProgress();
    }
    await refreshDetection();
  }

  boot().catch(() => setStatus(userMessage("UNSUPPORTED_PAGE"), "err"));
})();
