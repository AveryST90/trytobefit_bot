"""
Database layer — SQLite via Python's built-in sqlite3.
All data is stored in fitcoach.db in the bot's working directory.
"""

import sqlite3
from datetime import date, time, timedelta
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent / "fitcoach.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                phone     TEXT,
                notes     TEXT,
                created_at TEXT DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                session_date TEXT   NOT NULL,
                session_time TEXT   NOT NULL,
                duration    INTEGER NOT NULL DEFAULT 60,
                notes       TEXT,
                reminded_1h  INTEGER DEFAULT 0,
                reminded_2h  INTEGER DEFAULT 0,
                created_at   TEXT   DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workout_plans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                title       TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                created_at  TEXT    DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS trainer_chat (
                id      INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL
            );
        """)
        self.conn.commit()

    # ── Trainer chat ──────────────────────────────────────────────
    def set_trainer_chat(self, chat_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trainer_chat")
        cur.execute("INSERT INTO trainer_chat (id, chat_id) VALUES (1, ?)", (chat_id,))
        self.conn.commit()

    def get_trainer_chat(self) -> Optional[int]:
        cur = self.conn.cursor()
        row = cur.execute("SELECT chat_id FROM trainer_chat WHERE id=1").fetchone()
        return row["chat_id"] if row else None

    # ── Clients ───────────────────────────────────────────────────
    def get_all_clients(self) -> list:
        cur = self.conn.cursor()
        return [dict(r) for r in cur.execute(
            "SELECT * FROM clients ORDER BY name"
        ).fetchall()]

    def get_client(self, client_id: int) -> Optional[dict]:
        cur = self.conn.cursor()
        row = cur.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return dict(row) if row else None

    def add_client(self, name: str, phone: str, notes: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO clients (name, phone, notes) VALUES (?, ?, ?)",
            (name, phone, notes)
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_client(self, client_id: int):
        self.conn.execute("DELETE FROM clients WHERE id=?", (client_id,))
        self.conn.commit()

    def get_next_session_for_client(self, client_id: int) -> Optional[str]:
        today = date.today().isoformat()
        cur = self.conn.cursor()
        row = cur.execute(
            """SELECT session_date, session_time FROM sessions
               WHERE client_id=? AND session_date >= ?
               ORDER BY session_date, session_time LIMIT 1""",
            (client_id, today)
        ).fetchone()
        if row:
            return f"{row['session_date']} {row['session_time']}"
        return None

    # ── Sessions ──────────────────────────────────────────────────
    def add_session(self, client_id: int, session_date: date,
                    session_time: time, duration: int, notes: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO sessions (client_id, session_date, session_time, duration, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (client_id, session_date.isoformat(), session_time.strftime("%H:%M"), duration, notes)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_session(self, session_id: int) -> Optional[dict]:
        cur = self.conn.cursor()
        row = cur.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.id=?""",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_sessions_for_date(self, day: date) -> list:
        cur = self.conn.cursor()
        rows = cur.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date=?
               ORDER BY s.session_time""",
            (day.isoformat(),)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_range(self, start: date, end: date) -> list:
        cur = self.conn.cursor()
        rows = cur.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date BETWEEN ? AND ?
               ORDER BY s.session_date, s.session_time""",
            (start.isoformat(), end.isoformat())
        ).fetchall()
        return [dict(r) for r in rows]

    def get_upcoming_sessions(self, limit: int = 20) -> list:
        today = date.today().isoformat()
        cur = self.conn.cursor()
        rows = cur.execute(
            """SELECT s.*, c.name AS client_name FROM sessions s
               JOIN clients c ON c.id = s.client_id
               WHERE s.session_date >= ?
               ORDER BY s.session_date, s.session_time
               LIMIT ?""",
            (today, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: int):
        self.conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.conn.commit()

    def get_sessions_needing_reminder(self, hours_before: int) -> list:
        """Return sessions starting in ~hours_before hours that haven't been reminded yet."""
        from datetime import datetime
        now = datetime.now()
        target = now + timedelta(hours=hours_before)
        col = f"reminded_{hours_before}h"
        cur = self.conn.cursor()
        rows = cur.execute(
            f"""SELECT s.*, c.name AS client_name FROM sessions s
                JOIN clients c ON c.id = s.client_id
                WHERE s.{col} = 0
                  AND s.session_date = ?
                  AND s.session_time BETWEEN ? AND ?
                ORDER BY s.session_time""",
            (
                target.date().isoformat(),
                target.strftime("%H:%M"),
                (target + timedelta(minutes=1)).strftime("%H:%M"),
            )
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminded(self, session_id: int, hours_before: int):
        col = f"reminded_{hours_before}h"
        self.conn.execute(f"UPDATE sessions SET {col}=1 WHERE id=?", (session_id,))
        self.conn.commit()

    # ── Workout plans ─────────────────────────────────────────────
    def add_plan(self, client_id: int, title: str, content: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO workout_plans (client_id, title, content) VALUES (?, ?, ?)",
            (client_id, title, content)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_plans_for_client(self, client_id: int) -> list:
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT * FROM workout_plans WHERE client_id=? ORDER BY created_at DESC",
            (client_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_plans(self) -> list:
        cur = self.conn.cursor()
        rows = cur.execute(
            """SELECT wp.*, c.name AS client_name FROM workout_plans wp
               JOIN clients c ON c.id = wp.client_id
               ORDER BY wp.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
