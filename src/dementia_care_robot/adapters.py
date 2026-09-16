"""Simple console adapters used by development and the current prototype."""
import shutil
import subprocess
import threading

from .models import Assessment


class PiSpeaker:
    """Generate speech locally and play it through a selected ALSA output."""

    def __init__(self, device="default"):
        self.engine = shutil.which("espeak-ng")
        if not self.engine or not shutil.which("aplay"):
            raise ValueError("Pi speech requires espeak-ng and alsa-utils. Install them before enabling ROBOT_PI_SPEECH.")
        self.device = device
        self.lock = threading.Lock()

    def say(self, message: str) -> None:
        with self.lock:
            audio = subprocess.run(
                [self.engine, "--stdout", "--stdin"], input=message.encode("utf-8"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
            ).stdout
            subprocess.run(
                ["aplay", "-q", "-D", self.device], input=audio,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=120,
            )


class ConsoleSpeaker:
    def say(self, message: str) -> None:
        print(f"ROBOT: {message}")


class ConsoleCaregiverNotifier:
    """Demo only: printing is not a real or reliable notification."""

    def notify(self, assessment: Assessment) -> None:
        print(f"CAREGIVER ALERT [{assessment.risk.value.upper()}]: {assessment.reason}")
