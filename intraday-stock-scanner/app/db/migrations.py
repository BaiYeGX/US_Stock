from __future__ import annotations


def create_all(conn) -> None:
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS watchlist_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_date TEXT,
        symbol TEXT,
        pms_score REAL,
        pms_rank INTEGER,
        gap_pct REAL,
        pm_dollar_vol REAL,
        catalyst_score REAL,
        selected_flag INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        symbol TEXT,
        side TEXT,
        setup TEXT,
        score REAL,
        grade TEXT,
        entry_low REAL,
        entry_high REAL,
        stop REAL,
        tp1 REAL,
        tp2 REAL,
        risk_pct REAL,
        rr_tp1 REAL,
        rr_tp2 REAL,
        invalidate_if TEXT,
        reason TEXT,
        market_regime TEXT,
        raw_metrics_json TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS filter_rejections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        symbol TEXT,
        setup TEXT,
        reason TEXT,
        metrics_json TEXT
    )""")
    conn.commit()
