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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS followup_state (
                contact_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                last_user_message_at TIMESTAMP NOT NULL,
                scheduled_from_message_at TIMESTAMP NOT NULL,
                followup_scheduled_for TIMESTAMP,
                followup_sent_at TIMESTAMP,
                status TEXT NOT NULL CHECK(status IN (
                    'scheduled',
                    'sending',
                    'sent',
                    'skipped_user_replied',
                    'unsupported_channel',
                    'expired'
                )),
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_followup_state_due
            ON followup_state(status, followup_scheduled_for)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS handoff_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(contact_id, dedupe_key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS handoff_state (
                contact_id TEXT PRIMARY KEY,
                handoff_active INTEGER NOT NULL CHECK(handoff_active IN (0, 1)),
                activated_at TIMESTAMP,
                updated_at TIMESTAMP NOT NULL
            )
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


def upsert_followup_state(
    db_path: str,
    contact_id: str,
    channel: str,
    last_user_message_at: str,
    scheduled_from_message_at: str,
    followup_scheduled_for: str | None,
    status: str,
) -> None:
    updated_at = utcnow_iso()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO followup_state (
                contact_id,
                channel,
                last_user_message_at,
                scheduled_from_message_at,
                followup_scheduled_for,
                followup_sent_at,
                status,
                retry_count,
                last_error,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, NULL, ?, 0, NULL, ?)
            ON CONFLICT(contact_id) DO UPDATE SET
                channel = excluded.channel,
                last_user_message_at = excluded.last_user_message_at,
                scheduled_from_message_at = excluded.scheduled_from_message_at,
                followup_scheduled_for = excluded.followup_scheduled_for,
                followup_sent_at = NULL,
                status = excluded.status,
                retry_count = 0,
                last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (
                contact_id,
                channel,
                last_user_message_at,
                scheduled_from_message_at,
                followup_scheduled_for,
                status,
                updated_at,
            ),
        )


def get_due_followups(db_path: str, now_iso: str, limit: int = 100) -> list[dict[str, str]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                contact_id,
                channel,
                last_user_message_at,
                scheduled_from_message_at,
                followup_scheduled_for,
                retry_count
            FROM followup_state
            WHERE status = 'scheduled'
              AND followup_scheduled_for IS NOT NULL
              AND followup_scheduled_for <= ?
            ORDER BY followup_scheduled_for ASC
            LIMIT ?
            """,
            (now_iso, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def claim_followup_for_sending(
    db_path: str,
    contact_id: str,
    expected_scheduled_for: str,
    expected_last_user_message_at: str,
) -> bool:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE followup_state
            SET status = 'sending',
                updated_at = ?
            WHERE contact_id = ?
              AND status = 'scheduled'
              AND followup_scheduled_for = ?
              AND last_user_message_at = ?
            """,
            (
                utcnow_iso(),
                contact_id,
                expected_scheduled_for,
                expected_last_user_message_at,
            ),
        )
        return cur.rowcount == 1


def update_followup_status(
    db_path: str,
    contact_id: str,
    status: str,
    *,
    followup_sent_at: str | None = None,
    followup_scheduled_for: str | None = None,
    retry_count_increment: bool = False,
    last_error: str | None = None,
) -> None:
    retry_sql = "retry_count = retry_count + 1" if retry_count_increment else "retry_count = retry_count"
    with get_conn(db_path) as conn:
        conn.execute(
            f"""
            UPDATE followup_state
            SET status = ?,
                followup_sent_at = COALESCE(?, followup_sent_at),
                followup_scheduled_for = ?,
                {retry_sql},
                last_error = ?,
                updated_at = ?
            WHERE contact_id = ?
            """,
            (
                status,
                followup_sent_at,
                followup_scheduled_for,
                last_error,
                utcnow_iso(),
                contact_id,
            ),
        )


def requeue_stale_sending_followups(db_path: str, stale_before_iso: str) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE followup_state
            SET status = 'scheduled',
                updated_at = ?
            WHERE status = 'sending'
              AND updated_at <= ?
            """,
            (utcnow_iso(), stale_before_iso),
        )
        return cur.rowcount


def get_followup_state(db_path: str, contact_id: str) -> dict[str, str] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                contact_id,
                channel,
                last_user_message_at,
                scheduled_from_message_at,
                followup_scheduled_for,
                followup_sent_at,
                status,
                retry_count,
                last_error,
                updated_at
            FROM followup_state
            WHERE contact_id = ?
            """,
            (contact_id,),
        ).fetchone()

    if row is None:
        return None
    return dict(row)


def register_handoff_notification(db_path: str, contact_id: str, dedupe_key: str) -> bool:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO handoff_notifications(contact_id, dedupe_key, created_at)
            VALUES (?, ?, ?)
            """,
            (contact_id, dedupe_key, utcnow_iso()),
        )
        return cur.rowcount == 1


def is_handoff_active(db_path: str, contact_id: str) -> bool:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT handoff_active
            FROM handoff_state
            WHERE contact_id = ?
            """,
            (contact_id,),
        ).fetchone()
    if row is None:
        return False
    return bool(row["handoff_active"])


def activate_handoff(db_path: str, contact_id: str) -> bool:
    now = utcnow_iso()
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO handoff_state(contact_id, handoff_active, activated_at, updated_at)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(contact_id) DO UPDATE SET
                handoff_active = 1,
                activated_at = COALESCE(handoff_state.activated_at, excluded.activated_at),
                updated_at = excluded.updated_at
            WHERE handoff_state.handoff_active = 0
            """,
            (contact_id, now, now),
        )
        return cur.rowcount == 1
