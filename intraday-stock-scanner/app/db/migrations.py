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
    cur.execute("""CREATE TABLE IF NOT EXISTS position_states (
        symbol TEXT PRIMARY KEY,
        is_held INTEGER,
        entry_filled REAL,
        entry_date TEXT,
        held_position_size_shares INTEGER,
        r_init REAL,
        highest_close_since_entry REAL,
        stop0_t REAL,
        trail_stop_t REAL,
        holding_days INTEGER,
        updated_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS official_close_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange_date TEXT UNIQUE,
        snapshot_type TEXT,
        score_basis TEXT,
        payload_json TEXT,
        is_backfilled INTEGER DEFAULT 0,
        snapshot_generated_by TEXT DEFAULT 'auto',
        created_at TEXT,
        updated_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS interval_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT,
        slot_index INTEGER,
        slot_time TEXT,
        generated_at TEXT,
        symbol_count INTEGER,
        active_symbol_count INTEGER,
        top_symbols_json TEXT,
        avg_last_price REAL,
        alert_count INTEGER,
        payload_json TEXT,
        UNIQUE(trade_date, slot_index)
    )""")
    conn.commit()
