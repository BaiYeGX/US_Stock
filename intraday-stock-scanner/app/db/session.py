from __future__ import annotations

import sqlite3


def make_session_factory(database_url: str):
    if database_url.startswith("sqlite:///"):
        path = database_url.replace("sqlite:///", "")
    else:
        path = "scanner.db"

    def _connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    return _connect
