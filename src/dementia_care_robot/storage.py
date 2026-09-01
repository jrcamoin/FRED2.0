import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import ConversationTurn, FamiliarMedia, Reminder


class SQLiteStore:
    """Small local store. Production deployments should add encryption and access control."""

    def __init__(self, path: str | Path = "robot.db") -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _database(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._database() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY, message TEXT NOT NULL, due_at TEXT NOT NULL,
                    delivered_at TEXT
                );
                CREATE TABLE IF NOT EXISTS media (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, uri TEXT NOT NULL,
                    kind TEXT NOT NULL, description TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    def add_reminder(self, reminder: Reminder) -> None:
        with self._database() as db:
            db.execute(
                "INSERT INTO reminders(id, message, due_at) VALUES (?, ?, ?)",
                (reminder.reminder_id, reminder.message, reminder.due_at.astimezone(UTC).isoformat()),
            )

    def list_reminders(self, include_delivered: bool = False) -> list[Reminder]:
        query = "SELECT id, message, due_at FROM reminders"
        if not include_delivered:
            query += " WHERE delivered_at IS NULL"
        query += " ORDER BY due_at"
        with self._database() as db:
            return [Reminder(row["id"], row["message"], datetime.fromisoformat(row["due_at"])) for row in db.execute(query)]

    def due_reminders(self, now: datetime) -> list[Reminder]:
        with self._database() as db:
            rows = db.execute(
                "SELECT id, message, due_at FROM reminders WHERE delivered_at IS NULL AND due_at <= ? ORDER BY due_at",
                (now.astimezone(UTC).isoformat(),),
            )
            return [Reminder(row["id"], row["message"], datetime.fromisoformat(row["due_at"])) for row in rows]

    def mark_delivered(self, reminder_id: str, at: datetime) -> None:
        with self._database() as db:
            db.execute("UPDATE reminders SET delivered_at = ? WHERE id = ?", (at.astimezone(UTC).isoformat(), reminder_id))

    def add_media(self, media: FamiliarMedia) -> None:
        with self._database() as db:
            db.execute(
                "INSERT OR REPLACE INTO media(id, title, uri, kind, description) VALUES (?, ?, ?, ?, ?)",
                (media.media_id, media.title, media.uri, media.kind, media.description),
            )

    def list_media(self) -> list[FamiliarMedia]:
        with self._database() as db:
            return [FamiliarMedia(row["id"], row["title"], row["uri"], row["kind"], row["description"]) for row in db.execute("SELECT * FROM media ORDER BY title")]

    def append_turn(self, turn: ConversationTurn) -> None:
        with self._database() as db:
            db.execute("INSERT INTO conversation(role, content, created_at) VALUES (?, ?, ?)", (turn.role, turn.content, turn.at.isoformat()))

    def conversation(self, limit: int = 12) -> list[ConversationTurn]:
        with self._database() as db:
            rows = list(db.execute("SELECT role, content, created_at FROM conversation ORDER BY id DESC LIMIT ?", (limit,)))
        return [ConversationTurn(row["role"], row["content"], datetime.fromisoformat(row["created_at"])) for row in reversed(rows)]

    def clear_conversation(self) -> None:
        with self._database() as db:
            db.execute("DELETE FROM conversation")
