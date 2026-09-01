from .models import Assessment, CheckIn, FamiliarMedia, Reminder, RiskLevel
from .ports import CaregiverNotifier, MediaDisplay, Speaker
from .safety import SafetyPolicy


class CareCoordinator:
    def __init__(self, speaker: Speaker, notifier: CaregiverNotifier, policy: SafetyPolicy | None = None) -> None:
        self._speaker = speaker
        self._notifier = notifier
        self._policy = policy or SafetyPolicy()

    def deliver_reminder(self, reminder: Reminder) -> None:
        self._speaker.say(f"Hello. Here is your reminder: {reminder.message}")

    def handle_check_in(self, check_in: CheckIn) -> Assessment:
        assessment = self._policy.assess(check_in)
        self._speaker.say(assessment.supportive_message)
        if assessment.risk is not RiskLevel.ROUTINE:
            self._notifier.notify(assessment)
        return assessment

    def display_media(self, media: FamiliarMedia, display: MediaDisplay) -> None:
        display.show(media)
