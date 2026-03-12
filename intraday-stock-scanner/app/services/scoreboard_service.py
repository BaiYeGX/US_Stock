from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.constants import BENCHMARK_MAP, FIXED_SYMBOL_POOL, UNIQUE_SYMBOLS
from app.data.provider_service import MarketDataService
from app.services.local_position_store import LocalPositionStore
from app.services.market_time_service import MarketTimeService
from app.services.request_budget_manager import RequestBudgetManager
from app.services.score_engine import ScoreConfig, compute_symbol_score, rank_and_finalize


@dataclass
class RefreshConfig:
    preclose_quote_sec: int = 180
    last10m_quote_sec: int = 60
    candles_30m_sec: int = 900
    local_recalc_sec: int = 2


class ScoreBoardService:
    def __init__(self, session_factory) -> None:
        self.data_service = MarketDataService()
        self.budget = RequestBudgetManager()
        self.time_service = MarketTimeService()
        self.position_store = LocalPositionStore(session_factory)


    def _fetch_order(self, unique_symbols: list[str], positions: dict[str, dict]) -> list[str]:
        held = [s for s in unique_symbols if bool(positions.get(s, {}).get("isHeld", False))]
        remain = [s for s in unique_symbols if s not in held]
        return held + remain

    def _days_to_earnings(self, provider, symbol: str) -> int | None:
        today = datetime.now(tz=timezone.utc).date()
        end = today + timedelta(days=30)
        arr = provider.get_earnings_calendar(symbol, today.isoformat(), end.isoformat())
        if not arr:
            return None
        try:
            d = datetime.fromisoformat(arr[0]["date"]).date()
            return (d - today).days
        except Exception:
            return None

    def build_scoreboard(self, source: str, api_key: str, cfg: ScoreConfig | None = None) -> dict:
        cfg = cfg or ScoreConfig()
        provider = self.data_service._provider(source, api_key)
        # REST budget separation: count only HTTP calls made through data service/provider
        market_status_payload = provider.get_market_status() if hasattr(provider, "get_market_status") else {"market": "unknown"}
        self.budget.record_rest()
        market_state = self.time_service.classify_from_status(market_status_payload)

        positions = self.position_store.get_all()

        # deduped symbols only (12)
        unique_symbols = list(UNIQUE_SYMBOLS)
        daily_map: dict[str, list] = {}
        weekly_map: dict[str, list] = {}
        earnings_days: dict[str, int | None] = {}

        end = datetime.now(tz=timezone.utc)
        start_daily = end - timedelta(days=220)

        for symbol in self._fetch_order(unique_symbols, positions):
            if self.budget.can_call_rest():
                d = provider.get_historical_bars(symbol, "1d", start_daily, end)
                self.budget.record_rest()
            else:
                d = []
            daily_map[symbol] = d

            if self.budget.can_call_rest():
                w = provider.get_historical_bars(symbol, "1w", start_daily, end)
                self.budget.record_rest()
            else:
                w = []
            weekly_map[symbol] = w

            if self.budget.can_call_rest() and hasattr(provider, "get_earnings_calendar"):
                earnings_days[symbol] = self._days_to_earnings(provider, symbol)
                self.budget.record_rest()
            else:
                earnings_days[symbol] = None

        # benchmark mapping uses same dedup map without extra requests
        rows: list[dict] = []
        for symbol in FIXED_SYMBOL_POOL:
            b = BENCHMARK_MAP[symbol]
            pos = positions.get(symbol, {"isHeld": False})
            is_held = bool(pos.get("isHeld", False))
            row = compute_symbol_score(
                symbol=symbol,
                daily=daily_map.get(symbol, []),
                benchmark_daily=daily_map.get(b, []),
                benchmark_weekly=weekly_map.get(b, []),
                days_to_earnings=earnings_days.get(symbol),
                is_held=is_held,
                position=pos,
                cfg=cfg,
            )
            rows.append(row)

        ranked = rank_and_finalize(rows)
        not_ready_count = sum(1 for r in ranked if not r.get("BuyEligible") and (r.get("fields", {}).get("reason") is not None or r.get("hard_filters", {}).get("not_ready") is not None))

        candidate_count = sum(1 for r in ranked if not r["isHeld"] and r["CandidateAction"] in {"MUST_WATCH_BUY", "STRONG_WATCH_BUY", "BUY_SMALL_IF_TRIGGERED"})
        held_count = sum(1 for r in ranked if r["isHeld"])
        nextday_count = sum(1 for r in ranked if r["CandidateAction"] in {"MUST_WATCH_BUY", "STRONG_WATCH_BUY"})

        return {
            "rows": ranked,
            "overview": {
                "data_source": "Finnhub Free" if source == "finnhub" else source,
                "market_status": market_state.market_status,
                "is_open": market_state.is_open,
                "monitor_symbols": len(FIXED_SYMBOL_POOL),
                "candidate_count": candidate_count,
                "held_count": held_count,
                "nextday_watch_count": nextday_count,
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
                "rest_budget": self.budget.snapshot(),
                "not_ready_count": not_ready_count,
            },
        }
