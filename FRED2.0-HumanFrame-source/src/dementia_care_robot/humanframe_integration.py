"""Supported HumanFrame SDK integration for the FRED application.

Only status and microphone recording are currently consumed by FRED.
The SDK also has camera.capture(), but does not expose the live video stream
required by FRED's optional browser-based gaze tracker. No SDK speaker or Pico
motor control API exists in this version of HumanFrame Core.
"""

from pathlib import Path


class HumanFrameIntegration:
    AUDIO_DIR = Path("/opt/humanframe/data/audio")
    MAX_AUDIO_BYTES = 12_000_000

    def __init__(self, client=None):
        if client is None:
            from humanframe import HumanFrame
            client = HumanFrame()
        self.client = client

    def status(self):
        return self.client.status()

    def record_wav(self, duration=3):
        duration = int(duration)
        if not 1 <= duration <= 10:
            raise ValueError("Robot microphone duration must be between 1 and 10 seconds")
        result = self.client.audio.record(duration=duration)
        if result.get("success") is not True:
            raise RuntimeError("Robot microphone recording failed")
        path = result.get("path")
        if not isinstance(path, str):
            raise RuntimeError("HumanFrame returned no audio path")
        recording = Path(path).resolve(strict=True)
        # A Runtime response is not authorization to read arbitrary filesystem
        # paths. The Runtime contract returns WAVs under this fixed directory.
        if recording.parent != self.AUDIO_DIR.resolve() or recording.suffix != ".wav":
            raise RuntimeError("HumanFrame returned an unexpected audio path")
        try:
            if recording.stat().st_size > self.MAX_AUDIO_BYTES:
                raise RuntimeError("Robot microphone recording is too large")
            return recording.read_bytes()
        finally:
            # Do not accumulate identifiable resident audio on the robot.
            recording.unlink(missing_ok=True)
