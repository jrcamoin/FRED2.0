from .models import Assessment


class ConsoleSpeaker:
    def say(self, message: str) -> None:
        print(f"ROBOT: {message}")


class ConsoleCaregiverNotifier:
    """Demo only: printing is not a real or reliable notification."""

    def notify(self, assessment: Assessment) -> None:
        print(f"CAREGIVER ALERT [{assessment.risk.value.upper()}]: {assessment.reason}")
