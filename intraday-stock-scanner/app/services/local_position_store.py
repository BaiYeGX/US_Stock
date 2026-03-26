from __future__ import annotations

from datetime import datetime


class LocalPositionStore:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get_all(self) -> dict[str, dict]:
        with self.session_factory() as conn:
            conn.row_factory = __import__("sqlite3").Row
            cur = conn.cursor()
            cur.execute(
                "SELECT symbol,is_held,entry_filled,entry_date,held_position_size_shares,r_init,highest_close_since_entry,stop0_t,trail_stop_t,holding_days FROM position_states"
            )
            out: dict[str, dict] = {}
            for r in cur.fetchall():
                out[r["symbol"]] = {
                    "isHeld": bool(r["is_held"]),
                    "EntryFilled": r["entry_filled"],
                    "EntryDate": r["entry_date"],
                    "HeldPositionSizeShares": r["held_position_size_shares"],
                    "R_init": r["r_init"],
                    "HighestCloseSinceEntry": r["highest_close_since_entry"],
                    "Stop0_t": r["stop0_t"],
                    "TrailStop_t": r["trail_stop_t"],
                    "HoldingDays": r["holding_days"],
                }
            return out

    def upsert(self, symbol: str, payload: dict) -> None:
        with self.session_factory() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO position_states
                (symbol,is_held,entry_filled,entry_date,held_position_size_shares,r_init,highest_close_since_entry,stop0_t,trail_stop_t,holding_days,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    symbol,
                    int(bool(payload.get("isHeld", False))),
                    payload.get("EntryFilled"),
                    payload.get("EntryDate"),
                    payload.get("HeldPositionSizeShares", 0),
                    payload.get("R_init"),
                    payload.get("HighestCloseSinceEntry"),
                    payload.get("Stop0_t"),
                    payload.get("TrailStop_t"),
                    payload.get("HoldingDays", 0),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
