#!/bin/sh
# Run from the Pi desktop session so PipeWire sees the selected input/output.
set -eu

echo "Playback devices:"
aplay -l || true
echo "Capture devices:"
arecord -l || true
echo "Desktop audio routes:"
wpctl status || true
echo "Selected microphone:"
wpctl inspect @DEFAULT_AUDIO_SOURCE@ || true
echo "Selected speakers:"
wpctl inspect @DEFAULT_AUDIO_SINK@ || true

if [ "${1:-}" = "--record" ]; then
    command -v pw-record >/dev/null 2>&1 || { echo "Install PipeWire tools (pw-record)" >&2; exit 1; }
    command -v pw-play >/dev/null 2>&1 || { echo "Install PipeWire tools (pw-play)" >&2; exit 1; }
    echo "Recording five seconds from the selected PipeWire microphone..."
    python3 - <<'PY'
import signal
import subprocess
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="fred-microphone-") as directory:
    recording = Path(directory) / "recording.wav"
    process = subprocess.Popen(["pw-record", str(recording)])
    try:
        process.wait(timeout=5)
        raise SystemExit(f"Recording stopped early (exit {process.returncode}); check the microphone route")
    except subprocess.TimeoutExpired:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=5)
    if not recording.exists() or recording.stat().st_size < 1000:
        raise SystemExit("No usable audio was captured; check the microphone and USB data cable")
    print("Playing the recording through the selected PipeWire speakers...")
    subprocess.run(["pw-play", str(recording)], check=True)
PY
fi
