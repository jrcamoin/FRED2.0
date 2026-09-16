"""Send browser-recorded audio to an OpenAI-compatible transcription API."""

import json
import os
import secrets
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.request import Request, urlopen

from .api_errors import explain_api_error
from .config import local_ai_mode, offline_mode


class SpeechNotConfigured(RuntimeError):
    pass


class LocalTranscriber:
    """Decode browser clips and recognize speech locally, without API calls."""

    def __init__(self, model_path):
        if not Path(model_path).is_dir():
            raise SpeechNotConfigured("ROBOT_VOSK_MODEL must point to an extracted Vosk model directory. See README offline voice setup.")
        self.ffmpeg = shutil.which("ffmpeg")
        if not self.ffmpeg:
            raise SpeechNotConfigured("Offline microphone transcription requires ffmpeg: sudo apt install ffmpeg")
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError as error:
            raise SpeechNotConfigured('Install offline voice support: python -m pip install -e ".[offline-voice]"') from error
        try:
            self.model = Model(str(model_path))
        except Exception as error:
            raise SpeechNotConfigured("Unable to load ROBOT_VOSK_MODEL. Check that the model is fully extracted.") from error
        self.recognizer = KaldiRecognizer
        self.lock = threading.Lock()

    def transcribe(self, audio, content_type="audio/webm"):
        if not audio:
            raise ValueError("No audio was recorded")
        with self.lock:
            try:
                pcm = subprocess.run(
                    [self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                     "-protocol_whitelist", "pipe", "-i", "pipe:0", "-t", "60",
                     "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"],
                    input=audio, capture_output=True, check=True, timeout=45,
                ).stdout
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError("Could not decode the microphone recording. Try recording again.") from error
            recognizer = self.recognizer(self.model, 16000)
            parts = []
            for offset in range(0, len(pcm), 8000):
                if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
                    parts.append(json.loads(recognizer.Result()).get("text", ""))
            parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
            text = " ".join(part.strip() for part in parts if part.strip())
            if not text:
                raise ValueError("No speech was detected. Check the selected microphone and try again.")
            return text


def configured_transcriber():
    model_path = os.environ.get("ROBOT_VOSK_MODEL", "").strip()
    if model_path:
        return LocalTranscriber(Path(model_path).expanduser())
    return OpenAITranscriber.from_environment()


class OpenAITranscriber:
    """Transcribes one explicitly recorded audio clip; it never opens a microphone."""

    def __init__(self, api_key: str, model: str = "whisper-1", endpoint: str = "https://api.openai.com/v1/audio/transcriptions") -> None:
        self.api_key, self.model, self.endpoint = api_key, model, endpoint

    @classmethod
    def from_environment(cls) -> "OpenAITranscriber | None":
        """Build a transcriber only when remote speech processing is enabled."""
        if offline_mode() or local_ai_mode():
            return None
        key = os.environ.get("ROBOT_LLM_API_KEY")
        if not key:
            return None
        return cls(
            key,
            os.environ.get("ROBOT_TRANSCRIPTION_MODEL", "whisper-1"),
            os.environ.get("ROBOT_TRANSCRIPTION_ENDPOINT", "https://api.openai.com/v1/audio/transcriptions"),
        )

    def transcribe(self, audio: bytes, content_type: str = "audio/webm") -> str:
        if not audio:
            raise ValueError("No audio was recorded")
        boundary = "----FredAudio" + secrets.token_hex(12)
        extension = "ogg" if "ogg" in content_type else "mp4" if "mp4" in content_type else "webm"
        parts = [
            self._field(boundary, "model", self.model),
            self._file(boundary, "file", f"recording.{extension}", content_type, audio),
            f"--{boundary}--\r\n".encode(),
        ]
        request = Request(
            self.endpoint,
            data=b"".join(parts),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urlopen(request, timeout=45) as response:
                result = json.load(response)
        except Exception as error:
            raise explain_api_error(error, "Speech") from error
        text = str(result.get("text", "")).strip()
        if not text:
            raise ValueError("No speech was detected")
        return text

    @staticmethod
    def _field(boundary: str, name: str, value: str) -> bytes:
        return f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()

    @staticmethod
    def _file(boundary: str, name: str, filename: str, content_type: str, value: bytes) -> bytes:
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
        return header + value + b"\r\n"
