from datetime import UTC, datetime, timedelta

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
        local = at.astimezone()
        quiet_start = self.store.setting("quiet_start", "21:00")
        quiet_end = self.store.setting("quiet_end", "07:00")
        current = local.strftime("%H:%M")
        quiet = current >= quiet_start or current < quiet_end if quiet_start > quiet_end else quiet_start <= current < quiet_end
        if quiet:
            return []
        due = self.store.due_reminders(at)
        for reminder in due:
            self.coordinator.deliver_reminder(reminder)
            next_due = None
            if reminder.recurrence == "daily": next_due = reminder.due_at + timedelta(days=1)
            elif reminder.recurrence == "weekly": next_due = reminder.due_at + timedelta(days=7)
            self.store.mark_delivered(reminder.reminder_id, at, next_due)
        return due
