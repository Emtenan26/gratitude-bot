import sqlite3
import os
from datetime import datetime
import pytz

EGYPT_TZ = pytz.timezone("Africa/Cairo")
DB_PATH  = os.environ.get("DB_PATH", "gratitude_bot.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                name            TEXT,
                state           TEXT DEFAULT 'idle',
                morning_blessing TEXT,
                evening_sent_at TEXT,
                reminded        INTEGER DEFAULT 0,
                joined_at       TEXT
            )
        """)
        self.conn.commit()

    # ── Users ─────────────────────────────────────────────────────────────────

    def add_user(self, user_id: int, name: str):
        self.conn.execute("""
            INSERT OR IGNORE INTO users (user_id, name, joined_at)
            VALUES (?, ?, ?)
        """, (user_id, name, datetime.now(EGYPT_TZ).isoformat()))
        self.conn.commit()

    def user_exists(self, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is not None

    def get_all_users(self) -> list[int]:
        rows = self.conn.execute("SELECT user_id FROM users").fetchall()
        return [r[0] for r in rows]

    # ── State ─────────────────────────────────────────────────────────────────

    def get_user_state(self, user_id: int) -> str:
        row = self.conn.execute(
            "SELECT state FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else "idle"

    def set_user_state(self, user_id: int, state: str):
        self.conn.execute(
            "UPDATE users SET state = ? WHERE user_id = ?", (state, user_id)
        )
        self.conn.commit()

    # ── Morning ───────────────────────────────────────────────────────────────

    def set_morning_sent(self, user_id: int, blessing: str):
        self.conn.execute(
            "UPDATE users SET morning_blessing = ?, reminded = 0 WHERE user_id = ?",
            (blessing, user_id)
        )
        self.conn.commit()

    def get_morning_blessing(self, user_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT morning_blessing FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else None

    # ── Evening ───────────────────────────────────────────────────────────────

    def set_evening_sent_time(self, user_id: int):
        self.conn.execute(
            "UPDATE users SET evening_sent_at = ? WHERE user_id = ?",
            (datetime.now(EGYPT_TZ).isoformat(), user_id)
        )
        self.conn.commit()

    def get_evening_sent_time(self, user_id: int):
        row = self.conn.execute(
            "SELECT evening_sent_at FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    def clear_evening_data(self, user_id: int):
        self.conn.execute(
            "UPDATE users SET evening_sent_at = NULL, reminded = 0 WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()

    # ── Reminder ──────────────────────────────────────────────────────────────

    def was_reminded(self, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT reminded FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return bool(row[0]) if row else False

    def set_reminded(self, user_id: int):
        self.conn.execute(
            "UPDATE users SET reminded = 1 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()
