# FRED hardware integration

## Recommended roles

| Part | Role |
|---|---|
| Raspberry Pi 2 Model B v1.2 | Runs the Python web server, remote Whisper/LLM calls, storage, and LCD kiosk browser |
| Raspberry Pi Pico / RP2040 | Owns LED timing and reads physical switches over USB serial |
| LCD screen | HDMI display for the FRED dashboard; touch, mouse, or switches provide input |
| Microphone | Prefer a USB microphone or USB audio adapter connected to the device running the browser |
| Speakers | Connect to the tablet, HDMI display, USB audio adapter, or Pi analog output |
| Addressable LED ring | Connect to Pico; shows idle, listening, thinking, speaking, and alert states |
| Switches | Connect to Pico as HELP and ACTION inputs |

The current voice UI records through the browser. If Chromium runs in kiosk mode on the Pi, it uses the Pi's microphone and speakers. If the page runs on a tablet, it uses the tablet's microphone and speakers. The Pi 2 should call remote transcription and language-model services; it is not a practical target for running Whisper or a modern LLM locally.

## Pico default wiring

The defaults are at the top of `firmware/pico/main.py` and can be changed there.

| Function | Pico connection |
|---|---|
| LED ring data | GP16 through a suitable logic-level shifter when the ring is powered at 5 V |
| HELP switch | GP14 to switch, other switch terminal to GND |
| ACTION switch | GP15 to switch, other switch terminal to GND |
| Pi communication | Pico USB port to a Pi USB port, normally `/dev/ttyACM0` |

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
4. Connect the Pico to the Pi by USB and find its device:

```bash
ls -l /dev/ttyACM*
```

The Pico protocol is deliberately small:

```text
Pi -> Pico: LED idle|listening|thinking|speaking|alert|off
Pico -> Pi: SWITCH HELP PRESS
Pico -> Pi: SWITCH HELP RELEASE
```

Pressing HELP invokes the existing urgent caregiver-notification path. At present that notifier only logs to the Pi console; it is not an emergency service.

## Run on the Pi and LCD

Install Raspberry Pi OS, attach the LCD over HDMI, and connect the Pi to the internet using Ethernet or a compatible USB Wi-Fi adapter. The Pi 2 Model B does not provide the same built-in wireless setup as newer boards.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export ROBOT_LLM_API_KEY="your-key"
dementia-care-robot web --host 0.0.0.0 --pico /dev/ttyACM0
```

For the Pi-attached LCD, launch Chromium in kiosk mode at `http://127.0.0.1:8080`. Localhost is a secure browser context for microphone purposes. A separate tablet should use the HTTPS setup in the README.

## Before final wiring

Record the exact model or a clear photo of each LCD, microphone, speaker/amplifier, LED ring, switch, power supply, and Pico board. In particular, LED type, LED count, voltage, speaker amplification, microphone interface, and LCD input determine the final wiring and power design.
