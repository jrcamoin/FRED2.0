import threading
import termios
import tty
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO


class PicoBridge:
    """Line-oriented USB bridge to the Pico hardware controller."""

    VALID_STATES = {"idle", "listening", "thinking", "speaking", "alert", "off"}

    def __init__(self, device: str, on_event: Callable[[str, str], None], stream: BinaryIO | None = None) -> None:
        self.device, self.on_event = device, on_event
        self._stream = stream
        self._owns_stream = stream is None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._terminal_settings = None

    def start(self) -> None:
        if self._stream is None:
            self._stream = Path(self.device).open("r+b", buffering=0)
            if self._stream.isatty():
                self._terminal_settings = termios.tcgetattr(self._stream.fileno())
                tty.setraw(self._stream.fileno())
        self._thread = threading.Thread(target=self._read_loop, name="pico-bridge", daemon=True)
        self._thread.start()
        self.set_led("idle")

    def close(self) -> None:
        self._stop.set()
        if self._owns_stream and self._stream:
            if self._terminal_settings is not None:
                termios.tcsetattr(self._stream.fileno(), termios.TCSANOW, self._terminal_settings)
            self._stream.close()
        if self._thread:
            self._thread.join(timeout=1)

    def set_led(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"Unknown LED state: {state}")
        self._write(f"LED {state}\n".encode())

    def _write(self, data: bytes) -> None:
        if not self._stream:
            return
        with self._write_lock:
            self._stream.write(data)

    def _read_loop(self) -> None:
        assert self._stream is not None
        while not self._stop.is_set():
            try:
                line = self._stream.readline()
            except (OSError, ValueError):
                break
            if not line:
                if self._stop.wait(0.05):
                    break
                continue
            self.handle_line(line.decode(errors="replace"))

    def handle_line(self, line: str) -> None:
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == "SWITCH" and parts[2] in {"PRESS", "RELEASE"}:
            self.on_event(parts[1].lower(), parts[2].lower())
