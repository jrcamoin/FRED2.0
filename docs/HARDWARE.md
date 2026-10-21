# FRED hardware integration

## Recommended roles

| Part | Role |
|---|---|
| Raspberry Pi Compute Module 5 and I/O board | Runs the Python server, two Chromium windows, CSI camera/audio, storage, and AI integrations |
| Raspberry Pi Pico / RP2040 | Owns LED timing, neck servo trajectories, and physical switches over USB serial |
| Head LCD | Displays `/head`: expressive face, local camera gaze, and behavior state |
| Body LCD | Displays `/app`: conversation, reminders, photos, and touch controls |
| Raspberry Pi Camera | CSI camera on the I/O board; detect with `rpicam-hello --list-cameras` |
| Microphone | Prefer a USB microphone or USB audio adapter connected to the device running the browser |
| Speakers | Use the head LCD's HDMI audio output or a Pi USB audio adapter |
| Addressable LED ring | Connect to Pico; shows idle, listening, thinking, speaking, and alert states |
| Switches | Connect to Pico as HELP and ACTION inputs |

The current voice UI records through the browser. If Chromium runs in kiosk mode on the Pi, it uses the Pi's selected microphone and speakers. If the page runs on a tablet, it uses the tablet's microphone and speakers. HDMI can carry speaker audio to an LCD, but a microphone attached to the LCD needs a separate USB data path back to the Pi. CM5IO has no analog audio jack; use HDMI or USB audio output. See the [CM5 parts and power record](CM5_BUILD.md) before connecting the new regulators or servos.

## Pico default wiring

The defaults are at the top of `firmware/pico/main.py` and can be changed there.

| Function | Pico connection |
|---|---|
| LED ring data | GP16 through a suitable logic-level shifter when the ring is powered at 5 V |
| HELP switch | GP14 to switch, other switch terminal to GND |
| ACTION switch | GP15 to switch, other switch terminal to GND |
| Pan servo signal | GP18, disabled until the servo and mechanical limits are calibrated |
| Tilt servo signal | GP19, disabled until the servo and mechanical limits are calibrated |
| Pi communication | Pico USB data port to a Pi USB port; FRED discovers it automatically |

The switches use internal pull-ups and are active-low. Firmware debounce is included.
`SERVO_OUTPUT_ENABLED` is `False` in the Pico firmware. Fill every calibration
field and validate the separate servo supply before enabling PWM output.

Important electrical constraints:

- Confirm that the ring is a WS2812/NeoPixel-compatible part before using this firmware.
- Do not power an LED ring from a Pi or Pico 3.3 V GPIO pin.
- Use an appropriately rated external supply for the ring, sized for its LED count and maximum brightness.
- Join the Pico ground and LED-supply ground. Never join two positive supply rails.
- Add the capacitor and data-line resistor recommended by the LED-ring manufacturer.
- The official CM5IO can select 1.8 V or 3.3 V GPIO reference. Verify its
  setting before connecting any GPIO signal. The Pico uses 3.3 V logic; add
  appropriate level shifting if the carrier is set to 1.8 V. Never apply
  5 V directly to either GPIO input.
- Verify polarity and pin labels against the exact board and ring datasheets before applying power.

## Install the Pico firmware

1. Install MicroPython on the Pico.
2. Edit `LED_COUNT` and pin constants in `firmware/pico/main.py` to match the actual hardware.
3. Copy that file to the Pico as `main.py` using Thonny or `mpremote`.
4. Connect the Pico's data-capable USB port to the Pi, then run the diagnostic:

```bash
dementia-care-robot hardware-check
```

The Pico protocol is deliberately small:

```text
Pi -> Pico: LED idle|listening|thinking|speaking|alert|off
Pi -> Pico: NECK pan_degrees tilt_degrees speed_degrees_per_second
Pico -> Pi: SWITCH HELP PRESS
Pico -> Pi: SWITCH HELP RELEASE
```

Pressing HELP invokes the existing urgent caregiver-notification path. At present that notifier only logs to the Pi console; it is not an emergency service.

## Run on the Pi and LCD

Install 64-bit Raspberry Pi OS Desktop on the Compute Module 5 and attach both LCDs before boot so the desktop detects their layout. Raspberry Pi OS includes Python 3 and the desktop image includes Chromium. On the official CM5 I/O board, use its specified 5 V USB-C input; the newly purchased 12 V supply is not a direct input to that board. See the official [Compute Module hardware guide](https://www.raspberrypi.com/documentation/computers/compute-module.html).

```bash
sudo apt update
sudo apt install python3-venv python3-cryptography chromium alsa-utils pipewire-bin curl speech-dispatcher speech-dispatcher-espeak-ng
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --no-deps -e .
export ROBOT_LLM_API_KEY="your-key"
dementia-care-robot hardware-check
dementia-care-robot web --host 127.0.0.1 --pico auto
```

Using Raspberry Pi OS's `python3-cryptography` package avoids building that dependency during device setup. Verify the install before configuring startup:

```bash
python -c "from cryptography.fernet import Fernet; print('cryptography OK')"
python -m unittest discover -s tests -v
```

For current Raspberry Pi OS Desktop with labwc, follow the [CM5 two-screen startup guide](../deploy/pi5/README.md). It includes audio routing, window rules for both LCDs, graphical autostart, and a reboot check. The head is served on port 8081, while the main app stays on port 8080; `--head-port` changes the head port. Both share one robot state. First verify the CSI sensor with `rpicam-hello --list-cameras`, then test whether Chromium exposes that sensor to the head page. The current browser tracking uses `getUserMedia`; a camera reported by `rpicam-hello` is not proof that Chromium can capture it. Grant the head profile camera and microphone permission during setup, then tap **Enable Hey FRED** once. Tap **Show tracking** to see the live camera and a green box around the face FRED follows. Browser speech recognition requires Chromium support and may use an online provider; check the visible head status if speech or playback fails.

Chromium on Linux needs its speech-dispatcher launch flag for browser text-to-speech. If FRED shows a reply but speech playback fails, test `spd-say "Hello from FRED"` in the Pi desktop terminal. If that is silent, check the default output with `wpctl status` and select the head speakers. Close every Chromium window using the head profile before restarting it with `--enable-speech-dispatcher`; a new command may reuse an already running browser without applying a new flag.

If **Enable Hey FRED** reports a speech recognition `network` error despite working Pi internet, use **Tap to speak** on the head display. Tap once to start recording and again to send the question. This uses FRED's configured transcription endpoint instead of Chromium's speech recognition service, so set `ROBOT_LLM_API_KEY` on the Pi and run without `--offline` or `--local-ai`. Audio is sent to the configured transcription provider after the second tap. The wake phrase remains unavailable until Chromium speech recognition works or a local wake engine is added.

For an appliance-style installation, copy the repository to `/opt/fred`, create a dedicated `fred` system user, create `/var/lib/fred` owned by that user, install into `/opt/fred/.venv`, and install `deploy/fred.service` as `/etc/systemd/system/fred.service`. The supplied unit grants the standard `dialout`, `video`, and `audio` supplementary groups. Review the unit paths before starting it.

The supplied service uses automatic Pico discovery and prefers `/dev/serial/by-id/...` before trying `/dev/ttyACM*`. If more than one USB serial device is connected, set the Pico's stable path explicitly in `/opt/fred/.env`:

```bash
ls -l /dev/serial/by-id/
printf 'ROBOT_PICO_DEVICE=/dev/serial/by-id/YOUR_PICO_DEVICE\n' | sudo tee -a /opt/fred/.env
sudo systemctl daemon-reload
sudo systemctl enable --now fred
sudo systemctl status fred
```

If `hardware-check` reports `Pico access: permission denied`, verify that the running account has the `dialout` group, then sign out or restart the service so the new group is applied. If it reports no microphone or speaker, use `arecord -l` and `aplay -l` to confirm ALSA sees the USB audio device. A charge-only USB cable will power a Pico but will never create a serial device.

The caregiver dashboard reports network reachability, free storage, uptime, Pico connection, last resident check-in, and Raspberry Pi under-voltage/throttling when `vcgencmd` is installed. Treat an under-voltage warning as a power-supply or cable fault; do not hide it in production.

The resident ACTION switch acknowledges the currently displayed reminder. The HELP switch creates an urgent alert through configured SMS/push contacts. Test the entire notification chain—including a deliberately disconnected network—before every supervised pilot.

## Before final wiring

Record the exact model or a clear photo of each LCD, microphone, speaker/amplifier, LED ring, switch, power supply, and Pico board. In particular, LED type, LED count, voltage, speaker amplification, microphone interface, and LCD input determine the final wiring and power design.
