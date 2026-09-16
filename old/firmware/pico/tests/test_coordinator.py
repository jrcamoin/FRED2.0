import unittest
from datetime import UTC, datetime

from dementia_care_robot import CareCoordinator, CheckIn, Reminder, RiskLevel


class FakeSpeaker:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def say(self, message: str) -> None:
        self.messages.append(message)


class FakeNotifier:
    def __init__(self) -> None:
        self.assessments = []

    def notify(self, assessment) -> None:
        self.assessments.append(assessment)


class CareCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.speaker = FakeSpeaker()
        self.notifier = FakeNotifier()
        self.coordinator = CareCoordinator(self.speaker, self.notifier)
        self.now = datetime.now(UTC)

    def test_delivers_reminder(self) -> None:
        self.coordinator.deliver_reminder(Reminder("water", "Please drink water.", self.now))
        self.assertEqual(self.speaker.messages, ["Hello. Here is your reminder: Please drink water."])

    def test_routine_response_stays_local(self) -> None:
        result = self.coordinator.handle_check_in(CheckIn("I'm okay", self.now))
        self.assertEqual(result.risk, RiskLevel.ROUTINE)
        self.assertEqual(self.notifier.assessments, [])

    def test_possible_distress_notifies_caregiver(self) -> None:
        result = self.coordinator.handle_check_in(CheckIn("I feel confused", self.now))
        self.assertEqual(result.risk, RiskLevel.CAREGIVER)
        self.assertEqual(self.notifier.assessments, [result])

    def test_danger_is_urgent(self) -> None:
        result = self.coordinator.handle_check_in(CheckIn("I fell", self.now))
        self.assertEqual(result.risk, RiskLevel.URGENT)
        self.assertEqual(self.notifier.assessments, [result])

    def test_uncertain_or_missing_response_escalates(self) -> None:
        for response in (None, "maybe later"):
            with self.subTest(response=response):
                notifier = FakeNotifier()
                result = CareCoordinator(self.speaker, notifier).handle_check_in(CheckIn(response, self.now))
                self.assertEqual(result.risk, RiskLevel.CAREGIVER)
                self.assertEqual(notifier.assessments, [result])


if __name__ == "__main__":
    unittest.main()
