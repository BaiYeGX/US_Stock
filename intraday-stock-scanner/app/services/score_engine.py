from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.constants import BENCHMARK_MAP
from app.providers.base import Bar
from app.services.indicator_engine import (
    EPS,
    adx14,
    atr14,
    ema,
    highest,
    lowest,
    mean,
    pullback_days,
    rsi14,
    sanitize_number,
    sma,
)
from app.services.risk_engine import RiskConfig, compute_risk


def Up(x: float | None, a: float, b: float) -> float:
    if x is None or b - a == 0:
        return 0.0
    return min(1.0, max(0.0, (x - a) / (b - a)))


def Down(x: float | None, a: float, b: float) -> float:
    if x is None or b - a == 0:
        return 0.0
    return min(1.0, max(0.0, (b - x) / (b - a)))


def Center(x: float | None, m: float, w: float) -> float:
    if x is None or w == 0:
        return 0.0
    return min(1.0, max(0.0, 1 - abs(x - m) / w))


def I(cond: bool) -> float:
    return 1.0 if cond else 0.0


def clip100(x: float) -> float:
    return min(100.0, max(0.0, x))


@dataclass
class ScoreConfig:
    max_risk_usd: float = 12.0
    buy_threshold: float = 80.0
    half_buy_threshold: float = 70.0
    reduce_threshold: float = 55.0
    sell_threshold: float = 80.0
    hard_sell_threshold: float = 90.0
    target1_r: float = 2.0
    target2_r: float = 3.0
    trail_atr: float = 1.5
    max_holding_days: int = 5


def _ret(values: list[float], n: int) -> float | None:
    if len(values) <= n:
        return None
    prev = values[-1 - n]
    if abs(prev) <= EPS:
        return None
    return values[-1] / prev - 1


def _weekly_from_daily(daily: list[Bar]) -> list[Bar]:
    # compact by ISO year-week
    buckets: dict[tuple[int, int], list[Bar]] = {}
    for b in daily:
        iso = b.ts.isocalendar()
        key = (iso[0], iso[1])
        buckets.setdefault(key, []).append(b)
    out: list[Bar] = []
    for k in sorted(buckets):
        arr = buckets[k]
        out.append(
            Bar(
                symbol=arr[-1].symbol,
                ts=arr[-1].ts,
                open=arr[0].open,
                high=max(x.high for x in arr),
                low=min(x.low for x in arr),
                close=arr[-1].close,
                volume=sum(x.volume for x in arr),
            )
        )
    return out


def _not_ready_result(symbol: str, is_held: bool, reason: str) -> dict:
    candidate_action = "NO_BUY"
    position_action = "HOLD" if is_held else ""
    action = position_action if is_held else candidate_action
    return {
        "Symbol": symbol,
        "isHeld": is_held,
        "BuyEligible": False,
        "BuyScore": 0.0,
        "SellScore": None if not is_held else None,
        "CandidateAction": candidate_action,
        "PositionAction": position_action,
        "Action": action,
        "Entry": None,
        "Stop0": None,
        "TrailStop": None,
        "Target1": None,
        "Target2": None,
        "SuggestedPositionSizeShares": 0,
        "HeldPositionSizeShares": 0,
        "HoldingDays": None,
        "DaysToEarnings": None,
        "Risk_Reward_Ratio": None,
        "Rank": None,
        "grade_buy": "A0",
        "grade_sell": "S0" if is_held else None,
        "hard_filters": {"not_ready": reason},
        "buy_breakdown": {},
        "sell_breakdown": {},
        "fields": {"reason": reason},
    }


def compute_symbol_score(
    symbol: str,
    daily: list[Bar],
    benchmark_daily: list[Bar],
    benchmark_weekly: list[Bar],
    days_to_earnings: int | None,
    is_held: bool,
    position: dict | None,
    cfg: ScoreConfig,
) -> dict:
    if len(daily) < 30 or len(benchmark_daily) < 30:
        return _not_ready_result(symbol, is_held, "数据不足")

    closes = [b.close for b in daily]
    highs = [b.high for b in daily]
    lows = [b.low for b in daily]
    opens = [b.open for b in daily]
    vols = [b.volume for b in daily]

    sma5_t = sma(closes, 5)
    sma10_t = sma(closes, 10)
    sma20_t = sma(closes, 20)
    ema10_t = ema(closes, 10)
    atr14_t = atr14(daily, 14)
    adx14_t = adx14(daily, 14)
    rsi14_t = rsi14(closes, 14)
    avg_vol20 = mean(vols, 20)
    avg_dollar_vol20 = mean([c * v for c, v in zip(closes, vols)], 20)
    rvol20 = (vols[-1] / avg_vol20) if avg_vol20 and avg_vol20 > EPS else None
    clv_t = (closes[-1] - lows[-1]) / (highs[-1] - lows[-1] + EPS)
    ret3 = _ret(closes, 3)
    ret5 = _ret(closes, 5)

    bcloses = [b.close for b in benchmark_daily]
    bret3 = _ret(bcloses, 3)
    bret5 = _ret(bcloses, 5)
    er3 = None if ret3 is None or bret3 is None else ret3 - bret3
    er5 = None if ret5 is None or bret5 is None else ret5 - bret5

    hhv5_prev = highest(highs[:-1], 5)
    hhv20_prev = highest(highs[:-1], 20)
    llv3_t = lowest(lows, 3)
    pb_days = pullback_days(highs)
    pb_depth = None if hhv5_prev is None or llv3_t is None or atr14_t in (None, 0) else (hhv5_prev - llv3_t) / (atr14_t + EPS)
    pb_vol_ratio = None
    m3 = mean(vols, 3)
    m7_prev3 = mean(vols[:-3], 7)
    if m3 is not None and m7_prev3 is not None and m7_prev3 > EPS:
        pb_vol_ratio = m3 / m7_prev3

    weekly = _weekly_from_daily(daily)
    w_closes = [b.close for b in weekly]
    w_ema10 = ema(w_closes, 10)
    w_ema10_prev2 = ema(w_closes[:-2], 10) if len(w_closes) >= 12 else None
    weekly_up = bool(w_closes and w_ema10 is not None and w_ema10_prev2 is not None and w_closes[-1] > w_ema10 and w_ema10 > w_ema10_prev2)

    bw_closes = [b.close for b in benchmark_weekly]
    bw_ema10 = ema(bw_closes, 10)
    bw_ema10_prev2 = ema(bw_closes[:-2], 10) if len(bw_closes) >= 12 else None
    weekly_up_b = bool(bw_closes and bw_ema10 is not None and bw_ema10_prev2 is not None and bw_closes[-1] > bw_ema10 and bw_ema10 > bw_ema10_prev2)

    risk = compute_risk(highs[-1], llv3_t, sma20_t, atr14_t, RiskConfig(max_risk_usd=cfg.max_risk_usd, target1_r=cfg.target1_r, target2_r=cfg.target2_r))
    room20 = None
    if risk.entry is not None and risk.r_t not in (None, 0) and hhv20_prev is not None:
        room20 = 3.0 if risk.entry > hhv20_prev else (hhv20_prev - risk.entry) / (risk.r_t + EPS)

    # hard filters
    hf = {
        "C_t > SMA20_t": bool(closes[-1] > (sma20_t or 1e18)),
        "SMA5_t > SMA10_t > SMA20_t": bool((sma5_t or -1e18) > (sma10_t or 1e18) > (sma20_t or 1e18)),
        "WeeklyUpFlag": weekly_up,
        "DaysToEarnings >= 4": days_to_earnings is not None and days_to_earnings >= 4,
        "AvgDollarVol20_t >= 100,000,000": avg_dollar_vol20 is not None and avg_dollar_vol20 >= 100_000_000,
        "Entry_t > Stop0_t": risk.entry is not None and risk.stop0 is not None and risk.entry > risk.stop0,
        "SuggestedPositionSizeShares >= 1": risk.suggested_size >= 1,
    }
    buy_eligible = all(hf.values())

    # Buy sub scores
    qqq = benchmark_daily  # mapped benchmark already
    qcloses = [b.close for b in qqq]
    q_sma20 = sma(qcloses, 20)
    q_sma10 = sma(qcloses, 10)
    q_sma10_prev5 = sma(qcloses[:-5], 10) if len(qcloses) > 15 else None
    mr = 100 * (
        0.30 * Up((qcloses[-1] / (q_sma20 + EPS) - 1) if q_sma20 else None, 0.00, 0.03)
        + 0.25 * Up((q_sma10 / (q_sma10_prev5 + EPS) - 1) if q_sma10 and q_sma10_prev5 else None, 0.00, 0.02)
        + 0.25 * Up((bcloses[-1] / (sma(bcloses, 20) + EPS) - 1) if sma(bcloses, 20) else None, 0.00, 0.04)
        + 0.20 * I(weekly_up_b)
    )
    tq = 100 * (
        0.20 * Up((closes[-1] / (sma20_t + EPS) - 1) if sma20_t else None, 0.00, 0.08)
        + 0.15 * Up((sma5_t / (sma10_t + EPS) - 1) if sma5_t and sma10_t else None, 0.00, 0.03)
        + 0.15 * Up((sma10_t / (sma20_t + EPS) - 1) if sma10_t and sma20_t else None, 0.00, 0.05)
        + 0.15 * Up(adx14_t, 18, 35)
        + 0.20 * Up(er5, 0.00, 0.08)
        + 0.15 * I(weekly_up)
    )
    pq = 100 * (
        0.30 * Center(pb_depth, 1.20, 0.80)
        + 0.25 * Center(float(pb_days) if pb_days is not None else None, 2.00, 2.00)
        + 0.10 * Center(pb_vol_ratio, 0.75, 0.25)
        + 0.15 * Up((llv3_t / (sma20_t + EPS) - 1) if llv3_t and sma20_t else None, -0.01, 0.03)
        + 0.20 * Up((closes[-1] / (sma10_t + EPS) - 1) if sma10_t else None, -0.005, 0.03)
    )
    tg = 100 * (
        0.35 * I(closes[-1] > highs[-2])
        + 0.25 * Up(clv_t, 0.55, 0.90)
        + 0.20 * Up(rvol20, 1.00, 1.80)
        + 0.20 * Up((closes[-1] - highs[-2]) / (atr14_t + EPS) if atr14_t else None, 0.00, 0.40)
    )
    stop_atr = (risk.r_t / (atr14_t + EPS)) if risk.r_t and atr14_t else None
    tf = 100 * (
        0.40 * Up(room20, 1.50, 3.00)
        + 0.35 * Center(stop_atr, 1.20, 0.80)
        + 0.25 * I(risk.suggested_size >= 1)
    )
    gap_atr = ((opens[-1] - closes[-2]) / (atr14_t + EPS)) if atr14_t else None
    penalty = 25 * I(days_to_earnings is not None and days_to_earnings <= 3) + 15 * I(gap_atr is not None and gap_atr > 1.2) + 10 * I(((closes[-1] - (sma10_t or closes[-1])) / (atr14_t + EPS)) > 2.5 if atr14_t else False)

    buy_score = 0.0 if not buy_eligible else clip100(0.20 * mr + 0.25 * tq + 0.25 * pq + 0.15 * tg + 0.15 * tf - penalty)

    # Sell score
    sell_score = None
    position_action = ""
    sell_breakdown: dict[str, float | int] = {}
    trail_stop = position.get("TrailStop_t") if position else None
    held_shares = int(position.get("HeldPositionSizeShares", 0)) if position else 0
    entry_filled = position.get("EntryFilled") if position else None
    entry_date = position.get("EntryDate") if position else None
    r_init = position.get("R_init") if position else None
    highest_close = position.get("HighestCloseSinceEntry") if position else None
    holding_days = int(position.get("HoldingDays", 0)) if position else None

    if is_held:
        required_missing = [x for x in [entry_filled, entry_date, held_shares, r_init] if x in (None, "", 0)]
        if required_missing:
            sell_score = None
            position_action = "HOLD"
            sell_breakdown = {"not_ready": 1, "reason": "持仓记录不完整"}
        else:
            open_profit_r = (closes[-1] - float(entry_filled)) / (float(r_init) + EPS)
            trail_stop_val = trail_stop
            if trail_stop_val is None:
                trail_stop_val = max(float(entry_filled), (float(highest_close) if highest_close is not None else closes[-1]) - 1.5 * (atr14_t or 0), (sma10_t or closes[-1]) - 0.5 * (atr14_t or 0))

            # Hard exits
            if lows[-1] <= (risk.stop0 or -1e18):
                sell_score = 100.0
                position_action = "MUST_SELL"
            elif closes[-1] <= trail_stop_val:
                sell_score = 100.0
                position_action = "MUST_SELL"
            elif days_to_earnings is not None and days_to_earnings <= 1 and open_profit_r < 1.5:
                sell_score = 95.0
                position_action = "STRONG_SELL"
            elif holding_days is not None and holding_days >= 5 and open_profit_r < 1.0:
                sell_score = 90.0
                position_action = "STRONG_SELL"
            elif holding_days is not None and holding_days >= 7:
                sell_score = 100.0
                position_action = "MUST_SELL"
            else:
                sf_trend = 100 * (
                    0.30 * Down((closes[-1] / (sma10_t + EPS) - 1) if sma10_t else None, -0.03, 0.00)
                    + 0.30 * Down((closes[-1] / (sma20_t + EPS) - 1) if sma20_t else None, -0.05, 0.00)
                    + 0.20 * I((sma5_t or 0) < (sma10_t or 0))
                    + 0.20 * Down(((sma10_t or closes[-1]) / (sma(closes[:-3], 10) + EPS) - 1) if len(closes) > 13 and sma(closes[:-3], 10) else None, -0.02, 0.00)
                )
                sf_rs = 100 * (0.55 * Down(er3, -0.04, 0.00) + 0.45 * Down(er5, -0.06, 0.00))
                true_range_atr = ((highs[-1] - lows[-1]) / (atr14_t + EPS)) if atr14_t else None
                sf_dist = 100 * (
                    0.40 * I(closes[-1] < opens[-1] and vols[-1] > 1.3 * (avg_vol20 or 1e18))
                    + 0.30 * Down(clv_t, 0.35, 0.70)
                    + 0.30 * Up(true_range_atr, 1.00, 1.80)
                )
                sf_exhaust = 100 * (
                    0.35 * Up(rsi14_t, 72, 85)
                    + 0.35 * Up(((closes[-1] - (sma10_t or closes[-1])) / (atr14_t + EPS)) if atr14_t else None, 1.5, 3.0)
                    + 0.30 * I(open_profit_r >= 2.0 and clv_t < 0.35 and closes[-1] < highs[-1] * 0.99)
                )
                sf_time = 100 * (
                    0.60 * Up(float(holding_days), 3, 5) * Down(open_profit_r, 0.50, 1.50)
                    + 0.40 * I((holding_days or 0) >= 5 and open_profit_r < 1.0)
                )
                is_friday = daily[-1].ts.astimezone(timezone.utc).weekday() == 4
                sf_event = 100 * (
                    0.70 * I(days_to_earnings is not None and days_to_earnings <= 1)
                    + 0.30 * I(is_friday and open_profit_r < 1.0 and closes[-1] < (sma5_t or closes[-1]))
                )
                sell_score = clip100(0.30 * sf_trend + 0.20 * sf_rs + 0.15 * sf_dist + 0.15 * sf_exhaust + 0.10 * sf_time + 0.10 * sf_event)
                sell_breakdown = {
                    "SF_Trend": sf_trend,
                    "SF_RS": sf_rs,
                    "SF_Dist": sf_dist,
                    "SF_Exhaust": sf_exhaust,
                    "SF_Time": sf_time,
                    "SF_Event": sf_event,
                }
                if sell_score >= 90:
                    position_action = "MUST_SELL"
                elif sell_score >= 80:
                    position_action = "STRONG_SELL"
                elif sell_score >= 70:
                    position_action = "REDUCE_HARD"
                elif sell_score >= 55:
                    position_action = "REDUCE"
                else:
                    position_action = "HOLD"
            trail_stop = trail_stop_val

    # candidate action
    if buy_score >= 90 and buy_eligible:
        candidate_action = "MUST_WATCH_BUY"
    elif buy_score >= 80 and buy_eligible:
        candidate_action = "STRONG_WATCH_BUY"
    elif buy_score >= 70 and buy_eligible:
        candidate_action = "BUY_SMALL_IF_TRIGGERED"
    else:
        candidate_action = "NO_BUY"

    action = position_action if is_held else candidate_action

    grade_buy = "A0"
    if buy_score >= 90:
        grade_buy = "A5"
    elif buy_score >= 80:
        grade_buy = "A4"
    elif buy_score >= 70:
        grade_buy = "A3"
    elif buy_score >= 60:
        grade_buy = "A2"
    elif buy_score >= 50:
        grade_buy = "A1"

    grade_sell = None
    if sell_score is not None:
        if sell_score >= 90:
            grade_sell = "S5"
        elif sell_score >= 80:
            grade_sell = "S4"
        elif sell_score >= 70:
            grade_sell = "S3"
        elif sell_score >= 55:
            grade_sell = "S2"
        elif sell_score >= 40:
            grade_sell = "S1"
        else:
            grade_sell = "S0"

    return {
        "Symbol": symbol,
        "isHeld": is_held,
        "BuyEligible": buy_eligible,
        "BuyScore": round(buy_score, 2),
        "SellScore": None if sell_score is None else round(sell_score, 2),
        "CandidateAction": candidate_action,
        "PositionAction": position_action,
        "Action": action,
        "Entry": sanitize_number(risk.entry),
        "Stop0": sanitize_number(risk.stop0),
        "TrailStop": sanitize_number(trail_stop),
        "Target1": sanitize_number(risk.target1),
        "Target2": sanitize_number(risk.target2),
        "SuggestedPositionSizeShares": risk.suggested_size,
        "HeldPositionSizeShares": held_shares,
        "HoldingDays": holding_days,
        "DaysToEarnings": days_to_earnings,
        "Risk_Reward_Ratio": sanitize_number(room20),
        "Rank": None,
        "grade_buy": grade_buy,
        "grade_sell": grade_sell,
        "hard_filters": hf,
        "buy_breakdown": {
            "MR": round(mr, 2),
            "TQ": round(tq, 2),
            "PQ": round(pq, 2),
            "TG": round(tg, 2),
            "TF": round(tf, 2),
            "Penalty": round(penalty, 2),
        },
        "sell_breakdown": sell_breakdown,
        "fields": {
            "SMA5_t": sma5_t,
            "SMA10_t": sma10_t,
            "SMA20_t": sma20_t,
            "EMA10_t": ema10_t,
            "ATR14_t": atr14_t,
            "ADX14_t": adx14_t,
            "RSI14_t": rsi14_t,
            "AvgVol20_t": avg_vol20,
            "AvgDollarVol20_t": avg_dollar_vol20,
            "RVOL20_t": rvol20,
            "CLV_t": clv_t,
            "close": closes[-1],
            "Ret3_t": ret3,
            "Ret5_t": ret5,
            "ER3_t": er3,
            "ER5_t": er5,
            "HHV5_prev": hhv5_prev,
            "HHV20_prev": hhv20_prev,
            "LLV3_t": llv3_t,
            "PullbackDays": pb_days,
            "PBDepthATR_t": pb_depth,
            "PBVolRatio_t": pb_vol_ratio,
        },
    }


def rank_and_finalize(rows: list[dict]) -> list[dict]:
    sorted_rows = sorted(rows, key=lambda x: (x.get("BuyScore") or 0), reverse=True)
    for i, row in enumerate(sorted_rows, start=1):
        row["Rank"] = i
    return sorted_rows
