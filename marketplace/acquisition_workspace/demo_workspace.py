"""In-memory demo workspace for Acquisition Workspace UI evaluation.

Demo data is never persisted. Real candidates always take priority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from marketplace.acquisition_workspace.analysis_version import PROFIT_ANALYSIS_VERSION
from marketplace.acquisition_workspace.models import (
    AcquisitionCandidate,
    CandidateDataStatus,
    CandidateQualityGrade,
    CandidateState,
    ConfidenceLevel,
    DataTruthSummary,
    DiscoveryMetadata,
    RuntimeMode,
    SourceType,
    WorkspaceBatch,
)
from marketplace.acquisition_workspace.ranking import UsedListingRankResult

DEMO_BATCH_ID = "demo-workspace"
DEMO_SOURCE_NAME = "Demo Sample"


@dataclass(frozen=True, slots=True)
class DemoWorkspaceSnapshot:
    """Complete in-memory payload for rendering the demo dashboard."""

    batch: WorkspaceBatch
    rows: list[AcquisitionCandidate]
    ranking_by_id: dict[str, UsedListingRankResult]
    workspace_summary: dict
    grade_a: int
    grade_b: int
    grade_c: int
    eligible_count: int
    selling_estimate_by_id: dict[str, Decimal]
    detail_by_id: dict[str, dict]


class DemoWorkspaceProvider:
    """Build a realistic fictional workspace for UI review only."""

    @staticmethod
    def should_use_demo(*, current_rows: list, history: list | None = None, explicit_demo: bool = False) -> bool:
        """Return True only when demo mode is explicitly requested via ?demo=1.

        Operational UI never auto-injects sample data when the workspace is empty.
        Empty history/rows must never fall back to demo products.
        """
        del history  # retained for call-site compatibility; not used for activation
        del current_rows
        return explicit_demo is True

    @classmethod
    def build(cls) -> DemoWorkspaceSnapshot:
        specs = cls._demo_specs()
        rows = [cls._make_candidate(index, spec) for index, spec in enumerate(specs, start=1)]
        ranking_by_id = {
            row.candidate_id: cls._make_rank(index, row, spec)
            for index, (row, spec) in enumerate(zip(rows, specs), start=1)
        }
        selling_estimate_by_id = {
            row.candidate_id: spec["selling_jpy"]
            for row, spec in zip(rows, specs)
        }
        detail_by_id = {
            row.candidate_id: cls._demo_detail_payload(spec)
            for row, spec in zip(rows, specs)
        }
        needs_review = sum(1 for spec in specs if spec["needs_review"])
        profit_checked = sum(1 for spec in specs if spec["profit_checked"])
        grade_a = sum(1 for row in rows if row.quality_grade == CandidateQualityGrade.A.value)
        grade_b = sum(1 for row in rows if row.quality_grade == CandidateQualityGrade.B.value)
        grade_c = sum(1 for row in rows if row.quality_grade == CandidateQualityGrade.C.value)
        batch = WorkspaceBatch(
            workspace_batch_id=DEMO_BATCH_ID,
            name="デモワークスペース",
            source_type=SourceType.FIXTURE.value,
            created_at="2026-07-31T10:30:00+09:00",
            updated_at="2026-07-31T10:30:00+09:00",
            total_rows=len(rows),
            accepted_count=len(rows),
            warning_count=needs_review,
            rejected_count=0,
            duplicate_count=0,
            selected_count=0,
            status="DEMO",
        )
        return DemoWorkspaceSnapshot(
            batch=batch,
            rows=rows,
            ranking_by_id=ranking_by_id,
            workspace_summary={
                "candidates": len(rows),
                "accepted": len(rows),
                "pending": needs_review,
                "rejected": 0,
                "profit_checked": profit_checked,
                "average_profit": "¥24,560",
                "average_confidence": "高",
                "last_updated": "本日 10:30",
                "discovery_runtime": "DEMO",
                "acquisition_mode": "DEMO",
            },
            grade_a=grade_a,
            grade_b=grade_b,
            grade_c=grade_c,
            eligible_count=len(rows),
            selling_estimate_by_id=selling_estimate_by_id,
            detail_by_id=detail_by_id,
        )

    @classmethod
    def find_candidate(cls, candidate_id: str):
        """Return demo candidate, rank, selling estimate, and detail payload when present."""
        demo = cls.build()
        for row in demo.rows:
            if row.candidate_id == candidate_id:
                return {
                    "candidate": row,
                    "rank": demo.ranking_by_id.get(candidate_id),
                    "selling_estimate": demo.selling_estimate_by_id.get(candidate_id),
                    "detail": demo.detail_by_id.get(candidate_id, {}),
                    "batch": demo.batch,
                }
        return None

    @staticmethod
    def _demo_detail_payload(spec: dict) -> dict:
        """Static presentation fields for demo detail pages (offline sample data)."""
        purchase_jpy = int(spec["price_jpy"])
        selling_jpy = int(spec["selling_jpy"])
        profit_jpy = int(spec["net_profit"])
        purchase = f"¥{purchase_jpy:,}"
        selling = f"¥{selling_jpy:,}"
        profit = f"¥{profit_jpy:,}"
        # Allocate the exact residual so displayed costs reconcile to net profit.
        residual = selling_jpy - purchase_jpy - profit_jpy
        intl = min(4500, max(0, residual // 4))
        duty = min(3200, max(0, (residual - intl) // 3))
        tax = min(3000, max(0, (residual - intl - duty) // 3))
        domestic = min(800, max(0, (residual - intl - duty - tax) // 4))
        fee = min(12800, max(0, residual - intl - duty - tax - domestic - 1500))
        other = residual - intl - duty - tax - domestic - fee
        if other < 0:
            fee = max(0, fee + other)
            other = 0
        warnings = ["価格推定", "送料推定", "状態確認"]
        if spec["needs_review"]:
            warnings.append("付属品確認")
        return {
            "analysis": spec["analysis"],
            "warnings": tuple(warnings),
            "breakdown": [
                ("予測販売価格", selling),
                ("仕入価格", purchase),
                ("国際送料", f"¥{intl:,}"),
                ("関税", f"¥{duty:,}"),
                ("輸入消費税", f"¥{tax:,}"),
                ("国内送料", f"¥{domestic:,}"),
                ("Yahooオークション販売手数料", f"¥{fee:,}"),
                ("決済手数料", "¥0"),
                ("保険", "¥0"),
                ("梱包費", "¥0"),
                ("その他固定費", f"¥{other:,}"),
                ("最終利益", profit),
            ],
            "sales_info": [
                ("Sold件数", str(spec["sales"])),
                ("中央値", selling),
                ("最低価格", f"¥{int(spec.get('min_jpy', spec['selling_jpy'])):,}"),
                ("最高価格", f"¥{int(spec.get('max_jpy', spec['selling_jpy'])):,}"),
                ("Confidence", spec["confidence"]),
            ],
            "purchase_display": purchase,
        }

    @staticmethod
    def _demo_specs() -> list[dict]:
        return [
            {
                "slug": "chanel-wallet",
                "brand": "CHANEL",
                "title": "CHANEL マトラッセ キャビアスキン 長財布",
                "category": "Wallet",
                "price": Decimal("695"),
                "price_jpy": Decimal("104250"),
                "selling_jpy": Decimal("148000"),
                "min_jpy": Decimal("132000"),
                "max_jpy": Decimal("161000"),
                "net_profit": Decimal("32800"),
                "roi": Decimal("38"),
                "overall": Decimal("94"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 18,
                "analysis": "利益率が高く、販売実績も安定しています。購入前に状態と付属品をご確認ください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "lv-speedy",
                "brand": "Louis Vuitton",
                "title": "Louis Vuitton スピーディ25 モノグラム",
                "category": "Bag",
                "price": Decimal("980"),
                "price_jpy": Decimal("147000"),
                "selling_jpy": Decimal("205000"),
                "net_profit": Decimal("41200"),
                "roi": Decimal("34"),
                "overall": Decimal("91"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 22,
                "analysis": "定番モデルで回転が良く、比較価格も安定しています。シミとハンドル状態を重点確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "hermes-birkin-style",
                "brand": "Hermès",
                "title": "Hermès ガーデンパーティ TPM",
                "category": "Bag",
                "price": Decimal("1850"),
                "price_jpy": Decimal("277500"),
                "selling_jpy": Decimal("365000"),
                "net_profit": Decimal("52800"),
                "roi": Decimal("28"),
                "overall": Decimal("88"),
                "confidence": "中",
                "confidence_en": ConfidenceLevel.MEDIUM.value,
                "sales": 9,
                "analysis": "高単価で利益幅は大きい一方、真贋と付属品確認が重要です。要確認枠として残しています。",
                "needs_review": True,
                "profit_checked": True,
                "grade": CandidateQualityGrade.B.value,
            },
            {
                "slug": "gucci- Dionysus",
                "brand": "GUCCI",
                "title": "GUCCI ディオニュソス ショルダーバッグ",
                "category": "Bag",
                "price": Decimal("890"),
                "price_jpy": Decimal("133500"),
                "selling_jpy": Decimal("178000"),
                "net_profit": Decimal("29600"),
                "roi": Decimal("31"),
                "overall": Decimal("86"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 14,
                "analysis": "需要は安定しています。金具のくすみとストラップ摩耗を確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "celine-luggage",
                "brand": "CELINE",
                "title": "CELINE ラゲージ マイクロ ドラムドカーフ",
                "category": "Bag",
                "price": Decimal("1250"),
                "price_jpy": Decimal("187500"),
                "selling_jpy": Decimal("248000"),
                "net_profit": Decimal("36500"),
                "roi": Decimal("29"),
                "overall": Decimal("84"),
                "confidence": "中",
                "confidence_en": ConfidenceLevel.MEDIUM.value,
                "sales": 11,
                "analysis": "人気モデルですが相場変動があります。角スレと内側の汚れを優先確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.B.value,
            },
            {
                "slug": "dior-saddle",
                "brand": "Dior",
                "title": "Dior サドルバッグ オブリーク",
                "category": "Bag",
                "price": Decimal("1420"),
                "price_jpy": Decimal("213000"),
                "selling_jpy": Decimal("286000"),
                "net_profit": Decimal("44800"),
                "roi": Decimal("33"),
                "overall": Decimal("89"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 12,
                "analysis": "ブランド認知が高く再販しやすい候補です。金具の刻印とキャンバス状態を確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "prada-re-edition",
                "brand": "Prada",
                "title": "Prada Re-Edition ナイロン ショルダー",
                "category": "Bag",
                "price": Decimal("620"),
                "price_jpy": Decimal("93000"),
                "selling_jpy": Decimal("128000"),
                "net_profit": Decimal("21400"),
                "roi": Decimal("36"),
                "overall": Decimal("82"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 26,
                "analysis": "回転が早くROIも良好です。ナイロンの汚れとロゴプレートの傷を確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "fendi-baguette",
                "brand": "Fendi",
                "title": "Fendi バゲット ズッカ柄",
                "category": "Bag",
                "price": Decimal("760"),
                "price_jpy": Decimal("114000"),
                "selling_jpy": Decimal("154000"),
                "net_profit": Decimal("24100"),
                "roi": Decimal("27"),
                "overall": Decimal("79"),
                "confidence": "中",
                "confidence_en": ConfidenceLevel.MEDIUM.value,
                "sales": 8,
                "analysis": "クラシック需要はありますが比較件数が少なめです。真贋と金具状態を要確認としています。",
                "needs_review": True,
                "profit_checked": True,
                "grade": CandidateQualityGrade.B.value,
            },
            {
                "slug": "bottega-cassette",
                "brand": "Bottega Veneta",
                "title": "Bottega Veneta カセット イントレチャート",
                "category": "Bag",
                "price": Decimal("1180"),
                "price_jpy": Decimal("177000"),
                "selling_jpy": Decimal("242000"),
                "net_profit": Decimal("38900"),
                "roi": Decimal("32"),
                "overall": Decimal("87"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 15,
                "analysis": "見た目の希少性が高く利益見込みも良好です。編み込みの緩みと角擦れを確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
            {
                "slug": "ysl-loulou",
                "brand": "Saint Laurent",
                "title": "Saint Laurent ルル スモール キルティング",
                "category": "Bag",
                "price": Decimal("910"),
                "price_jpy": Decimal("136500"),
                "selling_jpy": Decimal("182000"),
                "net_profit": Decimal("27300"),
                "roi": Decimal("30"),
                "overall": Decimal("81"),
                "confidence": "高",
                "confidence_en": ConfidenceLevel.HIGH.value,
                "sales": 13,
                "analysis": "安定した需要が見込めます。チェーンの色落ちと内装の擦れを確認してください。",
                "needs_review": False,
                "profit_checked": True,
                "grade": CandidateQualityGrade.A.value,
            },
        ]

    @staticmethod
    def _make_candidate(index: int, spec: dict) -> AcquisitionCandidate:
        stamp = "2026-07-31T10:30:00+09:00"
        url = f"https://example.com/demo/{spec['slug']}"
        return AcquisitionCandidate(
            candidate_id=f"demo-{index:02d}-{spec['slug']}",
            workspace_batch_id=DEMO_BATCH_ID,
            title=spec["title"],
            normalized_title=spec["title"].lower(),
            brand=spec["brand"],
            category=spec["category"],
            detected_subtype=spec["category"].upper(),
            detected_material="",
            detected_model_tokens=(),
            detected_color="",
            detected_condition="EXCELLENT",
            purchase_price=spec["price"],
            currency="USD",
            purchase_price_jpy=spec["price_jpy"],
            purchase_url=url,
            source_name=DEMO_SOURCE_NAME,
            source_type=SourceType.FIXTURE.value,
            external_id=f"demo-{spec['slug']}",
            image_url="",
            seller_name="",
            location="",
            raw_description="UI evaluation sample. Not a real listing.",
            acquired_at=stamp,
            imported_at=stamp,
            data_status=CandidateDataStatus.FIXTURE.value,
            quality_score=90 if spec["grade"] == CandidateQualityGrade.A.value else 75,
            quality_grade=spec["grade"],
            validation_errors=(),
            validation_warnings=("付属品確認", "状態確認") if spec["needs_review"] else ("状態確認",),
            duplicate_of="",
            duplicate_reason="",
            eligible_for_profit_check=True,
            selected_for_profit_check=False,
            candidate_state=CandidateState.PROFIT_CHECKED.value,
            last_profit_batch_id="demo-profit",
            last_profit_checked_at=stamp if spec["profit_checked"] else "",
            last_decision="BUY",
            last_gross_profit=spec["net_profit"] + Decimal("5000"),
            last_net_profit=spec["net_profit"],
            last_warning="",
            data_truth_summary=DataTruthSummary(
                source_mode=RuntimeMode.FIXTURE.value,
                acquisition_mode="DEMO",
                market_source=DEMO_SOURCE_NAME,
                price_source="Demo Sample",
                comparable_source="Demo Comparables",
                shipping_source="Demo Estimate",
                fee_source="Demo Estimate",
                used_fixture_data=True,
                used_estimated_price=True,
                used_estimated_shipping=True,
                confidence_level=spec["confidence_en"],
                reasons=("Demo Workspace",),
            ),
            discovery_metadata=DiscoveryMetadata(
                discovery_timestamp=stamp,
                runtime_mode=RuntimeMode.FIXTURE.value,
                query_count=1,
                query_used=(spec["brand"],),
                candidate_count=1,
                comparable_count=spec["sales"],
                estimated_from_multiple_results=True,
                median_used=True,
                profit_analysis_version=PROFIT_ANALYSIS_VERSION if spec["profit_checked"] else "",
            ),
        )

    @staticmethod
    def _make_rank(index: int, row: AcquisitionCandidate, spec: dict) -> UsedListingRankResult:
        return UsedListingRankResult(
            candidate_id=row.candidate_id,
            title=row.title,
            rank=index,
            overall_score=spec["overall"],
            profit_score=spec["overall"],
            roi_score=spec["overall"],
            demand_score=spec["overall"],
            confidence_score=Decimal("100") if spec["confidence"] == "高" else Decimal("60"),
            net_profit=spec["net_profit"],
            roi=spec["roi"],
            sales_count=spec["sales"],
            confidence_level=spec["confidence"],
            source_listing_url=row.purchase_url,
            analysis_summary=spec["analysis"],
            ranking_warnings=("デモ表示",) if spec["needs_review"] else (),
        )
