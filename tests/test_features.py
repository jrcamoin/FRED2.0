import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dementia_care_robot.conversation import ConversationService, OfflineCompanion
from dementia_care_robot.coordinator import CareCoordinator
from dementia_care_robot.models import FamiliarMedia, Reminder, RiskLevel
from dementia_care_robot.scheduler import ReminderScheduler
from dementia_care_robot.storage import SQLiteStore


class FakeSpeaker:
    def __init__(self): self.messages = []
    def say(self, message): self.messages.append(message)


class FakeNotifier:
    def __init__(self): self.assessments = []
    def notify(self, assessment): self.assessments.append(assessment)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.temp.name) / "test.db")
        self.speaker, self.notifier = FakeSpeaker(), FakeNotifier()

    def tearDown(self): self.temp.cleanup()

    def test_due_reminders_deliver_once(self):
        scheduler = ReminderScheduler(self.store, CareCoordinator(self.speaker, self.notifier))
        now = datetime.now(UTC)
        scheduler.schedule(Reminder("due", "Drink water.", now - timedelta(seconds=1)))
        scheduler.schedule(Reminder("later", "Lunch time.", now + timedelta(hours=1)))
        self.assertEqual([r.reminder_id for r in scheduler.deliver_due(now)], ["due"])
        self.assertEqual(scheduler.deliver_due(now), [])
        self.assertEqual(len(self.speaker.messages), 1)

    def test_media_round_trip(self):
        media = FamiliarMedia("family", "Family picnic", "https://example.test/pic.jpg", description="Family at the park")
        self.store.add_media(media)
        self.assertEqual(self.store.list_media(), [media])

    def test_normal_conversation_does_not_alert(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("I used to grow roses", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertTrue(reply)
        self.assertEqual(self.notifier.assessments, [])

    def test_conversation_safety_bypasses_model_and_alerts(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("Help me, I fell", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.URGENT)
        self.assertIn("urgent help", reply)
        self.assertEqual(len(self.notifier.assessments), 1)

    def test_clear_conversation(self):
        ConversationService(self.store, OfflineCompanion(), self.notifier).respond("Hello", datetime.now(UTC))
        self.assertEqual(len(self.store.conversation()), 2)
        self.store.clear_conversation()
        self.assertEqual(self.store.conversation(), [])


if __name__ == "__main__": unittest.main()
