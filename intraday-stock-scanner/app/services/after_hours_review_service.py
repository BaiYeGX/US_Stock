from __future__ import annotations

from datetime import datetime, timezone

from app.data.provider_service import MarketDataService
from app.services.market_time_service import MarketTimeService


class AfterHoursReviewService:
    def __init__(self) -> None:
        self.data = MarketDataService()
        self.time = MarketTimeService()

    def build(self, source: str, api_key: str, official_snapshot: dict) -> dict:
        rows = official_snapshot.get("rows", [])
        out = []
        for r in rows:
            symbol = r.get("Symbol")
            entry_close = r.get("fields", {}).get("close") or r.get("Entry")
            q = self.data.get_quote(source, api_key, symbol, ttl=20)
            last_price = float(q.get("c", 0) or 0)
            base = float(entry_close or 0)
            change_pct = None
            if base > 0:
                change_pct = (last_price / base - 1) * 100
            risk = "低影响"
            if change_pct is not None and abs(change_pct) >= 2.5:
                risk = "高风险提示"
            elif change_pct is not None and abs(change_pct) >= 1:
                risk = "中等提示"
            out.append(
                {
                    "symbol": symbol,
                    "afterHoursLastPrice": last_price,
                    "afterHoursChangePctVsClose": change_pct,
                    "afterHoursRiskFlag": risk,
                    "afterHoursComment": "仅补充参考，不改写正式评分",
                }
            )

        return {
            "market_status_label_cn": official_snapshot.get("overview", {}).get("market_status", "未知"),
            "review_timestamp_shanghai": self.time.to_shanghai_display(datetime.now(tz=timezone.utc)),
            "items": out,
        }
