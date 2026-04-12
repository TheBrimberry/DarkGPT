"""
Signal Manager - SQLite-backed signal/trade history tracker.
Records every webhook signal, trade execution result, and tracks P&L.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "signals.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT DEFAULT 'tradingview',
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            order_type TEXT DEFAULT 'market',
            qty REAL,
            price REAL,
            stop_loss REAL,
            take_profit REAL,
            leverage INTEGER,
            raw_payload TEXT,
            status TEXT DEFAULT 'received',
            exchange_response TEXT,
            error_message TEXT,
            pnl REAL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            input_code TEXT NOT NULL,
            input_language TEXT,
            output_pinescript TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


class SignalManager:
    def __init__(self):
        init_db()

    def record_signal(self, payload: dict) -> int:
        conn = get_db()
        cur = conn.execute(
            """INSERT INTO signals
               (timestamp, source, symbol, action, order_type, qty, price,
                stop_loss, take_profit, leverage, raw_payload, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                payload.get("source", "tradingview"),
                payload.get("symbol", "UNKNOWN"),
                payload.get("action", "unknown"),
                payload.get("type", "market"),
                payload.get("qty"),
                payload.get("price"),
                payload.get("sl"),
                payload.get("tp"),
                payload.get("leverage"),
                json.dumps(payload),
                "received",
            ),
        )
        signal_id = cur.lastrowid
        conn.commit()
        conn.close()
        return signal_id

    def update_signal(self, signal_id: int, status: str, exchange_response: str = None, error: str = None, pnl: float = None):
        conn = get_db()
        conn.execute(
            """UPDATE signals
               SET status=?, exchange_response=?, error_message=?, pnl=?
               WHERE id=?""",
            (status, exchange_response, error, pnl, signal_id),
        )
        conn.commit()
        conn.close()

    def get_signals(self, limit: int = 50, offset: int = 0) -> list:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_signal(self, signal_id: int) -> dict:
        conn = get_db()
        row = conn.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        executed = conn.execute("SELECT COUNT(*) FROM signals WHERE status='executed'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM signals WHERE status='failed'").fetchone()[0]
        total_pnl = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM signals WHERE pnl IS NOT NULL").fetchone()[0]
        conn.close()
        return {
            "total_signals": total,
            "executed": executed,
            "failed": failed,
            "total_pnl": round(total_pnl, 4),
        }

    def clear_signals(self):
        conn = get_db()
        conn.execute("DELETE FROM signals")
        conn.commit()
        conn.close()

    # ── Chat History ─────────────────────────────────────────────────

    def save_chat_message(self, role: str, content: str):
        conn = get_db()
        conn.execute(
            "INSERT INTO chat_history (timestamp, role, content) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), role, content),
        )
        conn.commit()
        conn.close()

    def get_chat_history(self, limit: int = 50) -> list:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    def clear_chat_history(self):
        conn = get_db()
        conn.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()

    # ── Conversion History ───────────────────────────────────────────

    def save_conversion(self, input_code: str, input_language: str, output_pinescript: str):
        conn = get_db()
        conn.execute(
            "INSERT INTO conversions (timestamp, input_code, input_language, output_pinescript) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), input_code, input_language, output_pinescript),
        )
        conn.commit()
        conn.close()

    def get_conversions(self, limit: int = 20) -> list:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM conversions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Chart Data ───────────────────────────────────────────────────

    def get_chart_data(self, days: int = 14) -> dict:
        from collections import defaultdict
        modifier = f"-{days} days"
        conn = get_db()
        rows = conn.execute(
            """SELECT date(timestamp) as day, status,
                      COUNT(*) as count, COALESCE(SUM(pnl), 0) as day_pnl
               FROM signals
               WHERE date(timestamp) >= date('now', ?)
               GROUP BY day, status
               ORDER BY day ASC""",
            (modifier,),
        ).fetchall()
        conn.close()
        days_map: dict = defaultdict(lambda: {"executed": 0, "failed": 0, "received": 0, "pnl": 0.0})
        for row in rows:
            d = row["day"]
            days_map[d][row["status"]] = row["count"]
            if row["status"] == "executed":
                days_map[d]["pnl"] += row["day_pnl"]
        sorted_days = sorted(days_map.keys())
        return {
            "labels": sorted_days,
            "executed": [days_map[d]["executed"] for d in sorted_days],
            "failed": [days_map[d]["failed"] for d in sorted_days],
            "pnl": [round(days_map[d]["pnl"], 4) for d in sorted_days],
        }
