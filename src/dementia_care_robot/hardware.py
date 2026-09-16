"""Raspberry Pi diagnostics and the USB serial bridge to Pico firmware."""

import os
import platform
import shutil
import subprocess
import sys
import threading
import termios
import tty
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO


def discover_pico_device(dev_root: Path = Path("/dev")) -> str | None:
    """Find a Pico USB CDC device, preferring stable by-id names."""
    by_id = dev_root / "serial" / "by-id"
    stable = sorted(by_id.glob("*")) if by_id.is_dir() else []
    likely = [path for path in stable if any(word in path.name.lower() for word in ("pico", "rp2", "micropython"))]
    candidates = likely + [path for path in stable if path not in likely] + sorted(dev_root.glob("ttyACM*"))
    return str(candidates[0]) if candidates else None


def hardware_report(pico_device: str = "auto") -> list[tuple[str, bool, str]]:
    """Return Raspberry Pi hardware readiness checks without changing hardware."""
    model_path = Path("/proc/device-tree/model")
    model = model_path.read_text(errors="replace").rstrip("\x00\n") if model_path.is_file() else platform.platform()
    device = discover_pico_device() if pico_device == "auto" else pico_device
    pico_found = bool(device and Path(device).exists())
    pico_access = bool(pico_found and os.access(device, os.R_OK | os.W_OK))
    display = Path("/dev/fb0").exists() or Path("/dev/dri/card0").exists()
    playback, capture = _command_has_device("aplay"), _command_has_device("arecord")
    checks = [
        ("Model", "Raspberry Pi 3 Model B" in model, model),
        ("Python", sys.version_info >= (3, 11), platform.python_version()),
        ("Pico", pico_found, device or "not found; connect the Pico with a data-capable USB cable"),
        ("Pico access", pico_access, "read/write available" if pico_access else "device not found" if not pico_found else "permission denied; add the service user to dialout"),
        ("Display", display, "framebuffer/DRM detected" if display else "no framebuffer or DRM display detected"),
        ("Audio output", playback, "ALSA playback device detected" if playback else "no ALSA playback device detected; run aplay -l"),
        ("Microphone", capture, "ALSA capture device detected" if capture else "no ALSA capture device detected; run arecord -l"),
    ]
    if shutil.which("vcgencmd"):
        try:
            value = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2).stdout.strip()
            checks.append(("Power", value == "throttled=0x0", value or "unable to read throttling status"))
        except (OSError, subprocess.SubprocessError):
            checks.append(("Power", False, "vcgencmd failed"))
    return checks


def _command_has_device(command: str) -> bool:
    if not shutil.which(command):
        return False
    try:
        result = subprocess.run([command, "-l"], capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and "card " in result.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


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
        self.resolved_device: str | None = None
        self.last_error = ""

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
        """Reconnect indefinitely so unplugging the Pico does not stop FRED."""
        while not self._stop.is_set():
            try:
                resolved = discover_pico_device() if self.device == "auto" else self.device
                if not resolved:
                    raise FileNotFoundError("No Pico USB serial device found")
                self.resolved_device = resolved
                self._stream = Path(resolved).open("r+b", buffering=0)
                if self._stream.isatty():
                    self._terminal_settings = termios.tcgetattr(self._stream.fileno())
                    tty.setraw(self._stream.fileno())
                self._connected.set()
                self.last_error = ""
                self.set_led("idle")
                self._read_loop()
            except (OSError, ValueError) as error:
                self.last_error = str(error)
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
        """Parse the deliberately small `SWITCH name action` Pico protocol."""
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == "SWITCH" and parts[2] in {"PRESS", "RELEASE"}:
            self.on_event(parts[1].lower(), parts[2].lower())
