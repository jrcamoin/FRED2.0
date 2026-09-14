# FRED hardware integration

## Recommended roles

| Part | Role |
|---|---|
| Raspberry Pi 3 Model B v1.2 | Runs the Python web server, remote Whisper/LLM calls, storage, Wi-Fi/Ethernet, and LCD kiosk browser |
| Raspberry Pi Pico / RP2040 | Owns LED timing and reads physical switches over USB serial |
| LCD screen | HDMI display for the FRED dashboard; touch, mouse, or switches provide input |
| Microphone | Prefer a USB microphone or USB audio adapter connected to the device running the browser |
| Speakers | Connect to the tablet, HDMI display, USB audio adapter, or Pi analog output |
| Addressable LED ring | Connect to Pico; shows idle, listening, thinking, speaking, and alert states |
| Switches | Connect to Pico as HELP and ACTION inputs |

The current voice UI records through the browser. If Chromium runs in kiosk mode on the Pi, it uses the Pi's microphone and speakers. If the page runs on a tablet, it uses the tablet's microphone and speakers. The Pi 3 should call remote transcription and language-model services; it is not a practical target for running Whisper or a modern LLM locally.

## Pico default wiring

The defaults are at the top of `firmware/pico/main.py` and can be changed there.

| Function | Pico connection |
|---|---|
| LED ring data | GP16 through a suitable logic-level shifter when the ring is powered at 5 V |
| HELP switch | GP14 to switch, other switch terminal to GND |
| ACTION switch | GP15 to switch, other switch terminal to GND |
| Pi communication | Pico USB data port to a Pi USB port; FRED discovers it automatically |

The switches use internal pull-ups and are active-low. Firmware debounce is included.

Important electrical constraints:

- Confirm that the ring is a WS2812/NeoPixel-compatible part before using this firmware.
- Do not power an LED ring from a Pi or Pico 3.3 V GPIO pin.
- Use an appropriately rated external supply for the ring, sized for its LED count and maximum brightness.
- Join the Pico ground and LED-supply ground. Never join two positive supply rails.
- Add the capacitor and data-line resistor recommended by the LED-ring manufacturer.
- Keep all Pi/Pico GPIO at 3.3 V logic. Never apply 5 V directly to a GPIO input.
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
Pico -> Pi: SWITCH HELP PRESS
Pico -> Pi: SWITCH HELP RELEASE
```

Pressing HELP invokes the existing urgent caregiver-notification path. At present that notifier only logs to the Pi console; it is not an emergency service.

## Run on the Pi and LCD

Install the current Raspberry Pi OS Desktop image (Debian Trixie) for the Raspberry Pi 3 Model B v1.2 and attach the LCD over HDMI. Both 32-bit and 64-bit Raspberry Pi OS support the Pi 3; the 32-bit image leaves more of its 1 GB RAM available for Chromium. Raspberry Pi OS includes Python 3 and the desktop image includes Chromium. The Pi 3 Model B has built-in 2.4 GHz Wi-Fi and Ethernet. See the official [Raspberry Pi OS guide](https://www.raspberrypi.com/documentation/computers/os.html) and [Pi 3 Model B specifications](https://www.raspberrypi.com/products/raspberry-pi-3-model-b/).

```bash
sudo apt update
sudo apt install python3-venv python3-cryptography chromium alsa-utils
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --no-deps -e .
export ROBOT_LLM_API_KEY="your-key"
dementia-care-robot hardware-check
dementia-care-robot web --host 0.0.0.0 --pico auto
```

Using Raspberry Pi OS's `python3-cryptography` package avoids compiling Rust-backed cryptography code on the Pi 3. Verify the install before configuring startup:

```bash
python -c "from cryptography.fernet import Fernet; print('cryptography OK')"
python -m unittest discover -s tests -v
```

For the Pi-attached LCD, launch Chromium in kiosk mode with `chromium --kiosk --noerrdialogs --disable-session-crashed-bubble http://127.0.0.1:8080`. Localhost is a secure browser context for microphone capture. With a configured API key, the page records a single clip and sends it to the server transcription endpoint; without one, it uses browser speech recognition when Chromium provides it. Typed conversation remains available in either mode. A separate tablet should use the HTTPS setup in the README.

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
