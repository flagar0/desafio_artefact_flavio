"""Conversation persistence (SQLite) - one WhatsApp-like thread per customer.

Conversation modes:
  agent          -> the AI answers on its own (default)
  waiting_human  -> the agent asked for help; shopkeeper must take over (RED alert in the dashboard)
  human          -> shopkeeper took over; the agent stays silent
"""
import json
import sqlite3
from datetime import datetime

from app.config import CHAT_DB, STORAGE_DIR

AGENT, WAITING_HUMAN, HUMAN = "agent", "waiting_human", "human"


def _conn() -> sqlite3.Connection:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CHAT_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            customer_id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT 'agent',
            handoff_reason TEXT,
            handoff_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            sender TEXT NOT NULL,          -- customer | agent | human | system
            content TEXT NOT NULL,
            tools_used TEXT,               -- JSON list (agent messages only)
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id, id);
        """
    )
    return conn


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure(conn, customer_id: int) -> None:
    conn.execute("INSERT OR IGNORE INTO conversations(customer_id, updated_at) VALUES (?, ?)", (customer_id, _ts()))


def add_message(customer_id: int, sender: str, content: str, tools_used: list[str] | None = None) -> None:
    with _conn() as conn:
        _ensure(conn, customer_id)
        conn.execute(
            "INSERT INTO messages(customer_id, sender, content, tools_used, created_at) VALUES (?,?,?,?,?)",
            (customer_id, sender, content, json.dumps(tools_used) if tools_used else None, _ts()),
        )
        conn.execute("UPDATE conversations SET updated_at=? WHERE customer_id=?", (_ts(), customer_id))


def get_messages(customer_id: int, limit: int | None = None) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM messages WHERE customer_id=? ORDER BY id", (customer_id,)).fetchall()
    rows = [dict(r) for r in rows]
    return rows[-limit:] if limit else rows


def get_conversation(customer_id: int) -> dict:
    with _conn() as conn:
        _ensure(conn, customer_id)
        return dict(conn.execute("SELECT * FROM conversations WHERE customer_id=?", (customer_id,)).fetchone())


def list_conversations() -> dict[int, dict]:
    """customer_id -> conversation row + last message (only conversations that have messages)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT content FROM messages m WHERE m.customer_id=c.customer_id ORDER BY id DESC LIMIT 1) AS last_message "
            "FROM conversations c WHERE EXISTS (SELECT 1 FROM messages m WHERE m.customer_id=c.customer_id)"
        ).fetchall()
    return {r["customer_id"]: dict(r) for r in rows}


def request_handoff(customer_id: int, reason: str) -> None:
    with _conn() as conn:
        _ensure(conn, customer_id)
        conn.execute(
            "UPDATE conversations SET mode=?, handoff_reason=?, handoff_at=?, updated_at=? WHERE customer_id=?",
            (WAITING_HUMAN, reason, _ts(), _ts(), customer_id),
        )


def set_mode(customer_id: int, mode: str) -> None:
    with _conn() as conn:
        _ensure(conn, customer_id)
        conn.execute("UPDATE conversations SET mode=?, updated_at=? WHERE customer_id=?", (mode, _ts(), customer_id))
        if mode == AGENT:
            conn.execute("UPDATE conversations SET handoff_reason=NULL, handoff_at=NULL WHERE customer_id=?", (customer_id,))


def reset_conversation(customer_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM messages WHERE customer_id=?", (customer_id,))
        conn.execute("DELETE FROM conversations WHERE customer_id=?", (customer_id,))

