"""Human-readable acquisition workspace UI messaging helpers."""

from __future__ import annotations

from urllib.parse import quote, urlencode


_ERROR_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("captcha", "cf-challenge", "hcaptcha"), "CAPTCHAが表示されたため取得できませんでした。商品ページのURLを「商品URL追加」するか、CSVで取り込んでください。"),
    (("blocked", "policy_restriction", "blocked_by_site"), "サイトにブロックされたため取得できませんでした。商品URL追加またはCSVを使ってください。"),
    (("consent", "cookie", "didomi", "onetrust"), "同意画面のみが表示され、商品を取得できませんでした。"),
    (("login", "sign in", "auth0"), "ログインが必要なため取得できませんでした。"),
    (("timeout", "timed out", "network_error"), "通信がタイムアウトしました。時間をおいて再試行してください。"),
    (("malform", "unusable"), "HTMLが不正または解析不能です。別の保存HTMLを試してください。"),
    (("no product", "no results", "selector_not_found", "listings found"), "商品が見つかりませんでした。キーワードを変えるか保存HTMLを試してください。"),
    (("unsupported currency", "currency"), "対応していない通貨のため取り込めませんでした。"),
    (("no domestic", "no comparable", "no accepted comparable", "comparable not found"), "国内の比較対象が見つかりませんでした。"),
    (("missing required product url", "product url"), "商品ページURLを取得できなかったため取り込みを中止しました。"),
    (("invalid html",), "無効なHTMLです。検索結果ページの保存HTMLを指定してください。"),
)


def humanize_intake_error(raw: str | None, *, marketplace: str = "") -> str:
    """Map technical acquisition failures to short Japanese UI messages."""
    text = str(raw or "").strip()
    if not text:
        return f"{marketplace}の取得に失敗しました。" if marketplace else "取得に失敗しました。"
    lowered = text.lower()
    for needles, message in _ERROR_HINTS:
        if any(token in lowered for token in needles):
            return message
    # Never dump long tracebacks into the UI.
    if "traceback" in lowered or "file \"" in lowered:
        return f"{marketplace}の取得に失敗しました。保存HTMLを試してください。" if marketplace else "取得に失敗しました。"
    if len(text) > 180:
        return text[:177] + "..."
    return text


def workspace_intake_success_url(
    *,
    batch_id: str,
    marketplace: str,
    imported: int,
    rejected: int = 0,
    keyword: str = "",
) -> str:
    params = {
        "batch_id": batch_id,
        "intake_ok": "1",
        "marketplace": marketplace,
        "imported": str(imported),
        "rejected": str(max(0, rejected)),
    }
    if keyword:
        params["keyword"] = keyword
    return f"/acquisition-workspace?{urlencode(params)}"


def workspace_intake_error_url(message: str) -> str:
    return f"/acquisition-workspace?intake_error={quote(message)}"


def summarize_marketplace_runs(history: list) -> dict[str, dict[str, str]]:
    """Build last-run summaries for the four overseas acquisition panels from batch history."""
    markers = {
        "Fashionphile": ("Fashionphile",),
        "Rebag": ("Rebag",),
        "The RealReal": ("The RealReal", "RealReal"),
        "Vestiaire Collective": ("Vestiaire",),
    }
    summaries: dict[str, dict[str, str]] = {
        name: {"status": "未実行", "last_run": "-", "batch_id": ""} for name in markers
    }
    for batch in history or []:
        name = str(getattr(batch, "name", "") or "")
        updated = str(getattr(batch, "updated_at", "") or getattr(batch, "created_at", "") or "-")
        batch_id = str(getattr(batch, "workspace_batch_id", "") or "")
        total = getattr(batch, "total_rows", None)
        for marketplace, tokens in markers.items():
            if summaries[marketplace]["batch_id"]:
                continue
            if any(token.lower() in name.lower() for token in tokens):
                count = f"{total}件" if total is not None else ""
                summaries[marketplace] = {
                    "status": f"取込済 {count}".strip(),
                    "last_run": updated,
                    "batch_id": batch_id,
                }
    return summaries
