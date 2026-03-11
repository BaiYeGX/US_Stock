from __future__ import annotations


def make_daily_report(summary: dict) -> str:
    return "\n".join(["# Daily Review", f"total_alerts: {summary.get('total_alerts', 0)}", f"hit_tp1_rate: {summary.get('hit_tp1_rate', 0):.2f}"])
