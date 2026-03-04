import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_contact_created
            ON conversations(contact_id, created_at)
            """
        )


def add_message(db_path: str, contact_id: str, role: str, content: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO conversations(contact_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (contact_id, role, content, utcnow_iso()),
        )


def get_recent_messages(db_path: str, contact_id: str, limit: int = 30) -> list[dict[str, str]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM conversations
            WHERE contact_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (contact_id, limit),
        ).fetchall()

    # Reverse to send oldest -> newest to model.
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
