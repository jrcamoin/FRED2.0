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
        self._connected = threading.Event()
        self._write_lock = threading.Lock()
        self._terminal_settings = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> None:
        target = self._connection_loop if self._owns_stream else self._read_loop
        if not self._owns_stream:
            self._connected.set()
        self._thread = threading.Thread(target=target, name="pico-bridge", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._close_stream()
        if self._thread:
            self._thread.join(timeout=1)

    def _connection_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._stream = Path(self.device).open("r+b", buffering=0)
                if self._stream.isatty():
                    self._terminal_settings = termios.tcgetattr(self._stream.fileno())
                    tty.setraw(self._stream.fileno())
                self._connected.set()
                self.set_led("idle")
                self._read_loop()
            except (OSError, ValueError):
                pass
            finally:
                self._close_stream()
            self._stop.wait(2)

    def _close_stream(self) -> None:
        with self._write_lock:
            stream, self._stream = self._stream, None
            self._connected.clear()
            if not self._owns_stream or not stream:
                return
            try:
                if self._terminal_settings is not None:
                    termios.tcsetattr(stream.fileno(), termios.TCSANOW, self._terminal_settings)
                stream.close()
            except (OSError, ValueError, termios.error):
                pass
            finally:
                self._terminal_settings = None

    def set_led(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"Unknown LED state: {state}")
        self._write(f"LED {state}\n".encode())

    def _write(self, data: bytes) -> None:
        try:
            with self._write_lock:
                if not self._stream:
                    return
                self._stream.write(data)
        except (OSError, ValueError):
            self._connected.clear()

    def _read_loop(self) -> None:
        stream = self._stream
        assert stream is not None
        while not self._stop.is_set():
            try:
                line = stream.readline()
            except (OSError, ValueError):
                break
            if not line:
                break
            self.handle_line(line.decode(errors="replace"))

    def handle_line(self, line: str) -> None:
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == "SWITCH" and parts[2] in {"PRESS", "RELEASE"}:
            self.on_event(parts[1].lower(), parts[2].lower())
