from __future__ import annotations

import json

from app.alerts.schemas import AlertPlan


def render_json(plan: AlertPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2)


def render_text(plan: AlertPlan) -> str:
    et = plan.ts.strftime("%H:%M")
    return (
        f"[{et} ET] {plan.symbol} | {plan.side.upper()} | {plan.setup} | {plan.grade} | Score {plan.score}\n"
        f"Buy: {plan.entry_low:.2f} - {plan.entry_high:.2f}\n"
        f"Stop: {plan.stop:.2f}\n"
        f"TP1: {plan.tp1:.2f} | TP2: {plan.tp2:.2f}\n"
        f"Invalidate: {plan.invalidate_if}\n"
        f"Why: {plan.reason}"
    )
