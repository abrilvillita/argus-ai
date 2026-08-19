import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "argus.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_id TEXT NOT NULL DEFAULT '*',
            metric TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold REAL NOT NULL,
            action TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL,
            action_taken TEXT,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_telemetry_device
            ON telemetry (device_id, metric, created_at);
        """
    )
    conn.commit()
    conn.close()


def insert_telemetry(device_id: str, metric: str, value: float) -> float:
    ts = time.time()
    conn = get_conn()
    conn.execute(
        "INSERT INTO telemetry (device_id, metric, value, created_at) VALUES (?, ?, ?, ?)",
        (device_id, metric, value, ts),
    )
    conn.commit()
    conn.close()
    return ts


def recent_telemetry(device_id: str, metric: str, limit: int = 200) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT device_id, metric, value, created_at FROM telemetry
           WHERE device_id = ? AND metric = ?
           ORDER BY created_at DESC LIMIT ?""",
        (device_id, metric, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows][::-1]


def list_devices() -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT device_id, metric, value, created_at FROM telemetry t
           WHERE created_at = (
               SELECT MAX(created_at) FROM telemetry t2
               WHERE t2.device_id = t.device_id AND t2.metric = t.metric
           )
           ORDER BY device_id, metric"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_alert(device_id: str, metric: str, value: float, source: str, message: str, action_taken: str | None) -> dict[str, Any]:
    ts = time.time()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO alerts (device_id, metric, value, source, message, action_taken, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (device_id, metric, value, source, message, action_taken, ts),
    )
    conn.commit()
    alert_id = cur.lastrowid
    conn.close()
    return {
        "id": alert_id,
        "device_id": device_id,
        "metric": metric,
        "value": value,
        "source": source,
        "message": message,
        "action_taken": action_taken,
        "created_at": ts,
    }


def list_alerts(limit: int = 100) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_rule(name: str, device_id: str, metric: str, operator: str, threshold: float, action: str) -> dict[str, Any]:
    ts = time.time()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO rules (name, device_id, metric, operator, threshold, action, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
        (name, device_id, metric, operator, threshold, action, ts),
    )
    conn.commit()
    rule_id = cur.lastrowid
    conn.close()
    return {
        "id": rule_id,
        "name": name,
        "device_id": device_id,
        "metric": metric,
        "operator": operator,
        "threshold": threshold,
        "action": action,
        "enabled": True,
        "created_at": ts,
    }


def list_rules() -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM rules ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_rule(rule_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
