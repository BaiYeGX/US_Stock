from __future__ import annotations


def room_multiple(available_room: float, risk_distance: float) -> float:
    if risk_distance <= 0:
        return 0.0
    return available_room / risk_distance
