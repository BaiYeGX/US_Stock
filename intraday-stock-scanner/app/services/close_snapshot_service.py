from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.migrations import create_all
from app.services.market_time_service import MarketTimeService
from app.services.scoreboard_service import ScoreBoardService


class CloseSnapshotService:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.scoreboard = ScoreBoardService(session_factory)
        self.time_service = MarketTimeService()

    def _ensure_schema(self) -> None:
        with self.session_factory() as conn:
            create_all(conn)

    def get_latest(self) -> dict | None:
        self._ensure_schema()
        with self.session_factory() as conn:
            cur = conn.cursor()
            cur.execute("SELECT exchange_date,payload_json,is_backfilled,snapshot_generated_by,created_at,updated_at FROM official_close_snapshots ORDER BY exchange_date DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            payload = json.loads(row[1])
            payload["meta"] = {
                "exchange_date": row[0],
                "is_backfilled": bool(row[2]),
                "snapshot_generated_by": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }
            return payload

    def get_by_date(self, exchange_date: str) -> dict | None:
        self._ensure_schema()
        with self.session_factory() as conn:
            cur = conn.cursor()
            cur.execute("SELECT payload_json,is_backfilled,snapshot_generated_by,created_at,updated_at FROM official_close_snapshots WHERE exchange_date=?", (exchange_date,))
            row = cur.fetchone()
            if not row:
                return None
            payload = json.loads(row[0])
            payload["meta"] = {
                "exchange_date": exchange_date,
                "is_backfilled": bool(row[1]),
                "snapshot_generated_by": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            return payload

    def capture(self, source: str, api_key: str, generated_by: str = "auto", is_backfilled: bool = False, force: bool = False) -> dict:
        self._ensure_schema()
        provider = self.scoreboard.data_service._provider(source, api_key)
        market_status = provider.get_market_status() if hasattr(provider, "get_market_status") else {"market":"unknown"}
        snapshot = self.scoreboard.build_scoreboard(source=source, api_key=api_key)
        exchange_date = self.time_service.get_latest_completed_exchange_date(market_status)
        now_ny = self.time_service.now_ny()
        now_sh = self.time_service.now_shanghai()
        payload = {
            "snapshot_type": "official_close_snapshot",
            "score_basis": "official_close",
            "exchange_date": exchange_date,
            "exchange_close_timestamp_ny": f"{exchange_date}T16:00:00-05:00",
            "snapshot_generated_timestamp_ny": now_ny.isoformat(),
            "snapshot_generated_timestamp_shanghai": now_sh.isoformat(),
            "local_saved_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "snapshot_generated_by": generated_by,
            "is_backfilled": bool(is_backfilled),
            **snapshot,
        }
        payload.setdefault("overview", {})["score_basis_note"] = "主评分依据：前一交易日正式收盘快照"

        created = False
        with self.session_factory() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM official_close_snapshots WHERE exchange_date=?", (exchange_date,))
            old = cur.fetchone()
            if old and not force:
                return {"ok": True, "created": False, "exchange_date": exchange_date, "payload": self.get_by_date(exchange_date)}
            if old:
                cur.execute(
                    "UPDATE official_close_snapshots SET payload_json=?, is_backfilled=?, snapshot_generated_by=?, updated_at=? WHERE exchange_date=?",
                    (json.dumps(payload, ensure_ascii=False), int(is_backfilled), generated_by, datetime.now().isoformat(), exchange_date),
                )
            else:
                created = True
                cur.execute(
                    "INSERT INTO official_close_snapshots (exchange_date,snapshot_type,score_basis,payload_json,is_backfilled,snapshot_generated_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        exchange_date,
                        "official_close_snapshot",
                        "official_close",
                        json.dumps(payload, ensure_ascii=False),
                        int(is_backfilled),
                        generated_by,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )
            conn.commit()

        file_status = self._write_files(exchange_date, payload)
        return {"ok": True, "created": created, "exchange_date": exchange_date, "payload": payload, "file_status": file_status}

    def backfill_latest(self, source: str, api_key: str) -> dict:
        return self.capture(source=source, api_key=api_key, generated_by="backfill", is_backfilled=True, force=True)

    def _write_files(self, exchange_date: str, payload: dict) -> dict:
        out_dir = Path("data/snapshots")
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"official-close-snapshot-{exchange_date}.json"
        txt_path = out_dir / f"official-close-summary-{exchange_date}.txt"
        status = {"json_ok": False, "txt_ok": False, "errors": []}

        try:
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            status["json_ok"] = True
        except Exception as exc:  # pragma: no cover
            status["errors"].append(f"json写入失败: {exc}")

        try:
            rows = payload.get("rows", [])
            top3 = rows[:3]
            lines = [
                f"交易所日期(纽约): {exchange_date}",
                f"快照生成时间(上海): {payload.get('snapshot_generated_timestamp_shanghai')}",
                f"快照生成时间(纽约): {payload.get('snapshot_generated_timestamp_ny')}",
                "Top3:",
            ]
            lines.extend([f"- {x.get('Symbol')} Buy={x.get('BuyScore')} Sell={x.get('SellScore')} Action={x.get('Action')}" for x in top3])
            lines.append("\n全部标的:")
            for x in rows:
                lines.append(
                    f"{x.get('Symbol')} | Buy={x.get('BuyScore')} Sell={x.get('SellScore')} | Action={x.get('Action')} | Entry={x.get('Entry')} Stop0={x.get('Stop0')} Target1={x.get('Target1')} Target2={x.get('Target2')}"
                )
            txt_path.write_text("\n".join(lines), encoding="utf-8")
            status["txt_ok"] = True
        except Exception as exc:  # pragma: no cover
            status["errors"].append(f"txt写入失败: {exc}")

        return status
