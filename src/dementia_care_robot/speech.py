import json
import os
import secrets
from urllib.request import Request, urlopen


class SpeechNotConfigured(RuntimeError):
    pass


class OpenAITranscriber:
    """Transcribes one explicitly recorded audio clip; it never opens a microphone."""

    def __init__(self, api_key: str, model: str = "whisper-1", endpoint: str = "https://api.openai.com/v1/audio/transcriptions") -> None:
        self.api_key, self.model, self.endpoint = api_key, model, endpoint

    @classmethod
    def from_environment(cls) -> "OpenAITranscriber | None":
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
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
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
