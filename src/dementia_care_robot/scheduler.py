from datetime import UTC, datetime

from .coordinator import CareCoordinator
from .models import Reminder
from .storage import SQLiteStore


class ReminderScheduler:
    def __init__(self, store: SQLiteStore, coordinator: CareCoordinator) -> None:
        self.store, self.coordinator = store, coordinator

    def schedule(self, reminder: Reminder) -> None:
        if not reminder.message.strip():
            raise ValueError("Reminder message is required")
        if reminder.due_at.tzinfo is None:
            raise ValueError("Reminder time must include a timezone")
        self.store.add_reminder(reminder)

    def deliver_due(self, now: datetime | None = None) -> list[Reminder]:
        at = now or datetime.now(UTC)
        due = self.store.due_reminders(at)
        for reminder in due:
            self.coordinator.deliver_reminder(reminder)
            self.store.mark_delivered(reminder.reminder_id, at)
        return due
