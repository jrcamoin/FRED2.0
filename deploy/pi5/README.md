# Compute Module 5 two-screen startup

This setup targets a Compute Module 5 on a compatible I/O board with 64-bit
Raspberry Pi OS Desktop and the default labwc Wayland session. The Python backend runs as the `fred` system user; Chromium
runs in the desktop user's graphical session. These files have not yet been
validated on the assembled robot.

## 1. Connect and check hardware

Connect both LCDs before boot. A touchscreen may also need a USB data
cable. HDMI carries video and possibly speaker audio **from** the Pi; it does
not carry microphone audio back to the Pi. A microphone plugged into an LCD
must have a USB data path from that LCD to the Pi, or be connected to a Pi USB
audio adapter directly.

Run from a terminal in the Pi desktop session:

```bash
wlr-randr
/opt/fred/deploy/pi5/check-audio.sh
/opt/fred/deploy/pi5/check-audio.sh --record
/opt/fred/.venv/bin/dementia-care-robot hardware-check
```

Use `wpctl status` to identify the input and output devices. Select the
microphone and the head LCD speakers as desktop defaults with
`wpctl set-default <ID>` for each device, then repeat the record/playback
test. The script records through PipeWire, the desktop audio route used by
Chromium, and deletes the temporary clip afterward. Check the body touchscreen
and CSI camera separately with `rpicam-hello --list-cameras`. Record
the actual output names printed by `wlr-randr`; connector order may not
match physical screen position.

The [CM5 build record](../../docs/CM5_BUILD.md) covers the camera connector,
new power rails, servos, and mechanical parts. If this is the official CM5IO,
power it with a validated 5 V USB-C supply during initial setup; do not
connect the 12 V supply directly to the board.

## 2. Start the backend at boot

Install the package into `/opt/fred/.venv` and ensure `/var/lib/fred` exists
and is owned by the `fred` system user, as described in
[`docs/HARDWARE.md`](../../docs/HARDWARE.md). Copy
[`deploy/fred.service`](../fred.service) into `/etc/systemd/system/`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fred
systemctl status fred
curl --fail http://127.0.0.1:8080/app >/dev/null
curl --fail http://127.0.0.1:8081/ >/dev/null
```

The supplied service listens only on Pi loopback and requires caregiver
authentication. Open `http://127.0.0.1:8080/caregiver` on the Pi once to set
the caregiver password, quiet hours, and a contact. The resident UI remains
available without signing in.

## 3. Put each window on its LCD

Install `chromium`, `curl`, `alsa-utils`, `pipewire-bin`, `speech-dispatcher`, and
`speech-dispatcher-espeak-ng` if missing. Keep two persistent Chromium
profiles so camera and microphone permissions survive reboot.

In the desktop user's `~/.config/labwc/rc.xml`, add a `<windowRules>` section
inside `<labwc_config>` if one is not already present. Insert the two rules
from [`labwc-window-rules.xml`](labwc-window-rules.xml) into that section,
changing `HDMI-A-1` and `HDMI-A-2` to the output names from `wlr-randr`.
The rules move each app window before making it full screen.

In the same desktop user's `~/.config/labwc/autostart`, add:

```sh
/opt/fred/deploy/pi5/start-displays.sh &
```

Set the Pi to boot to the desktop with automatic login for this dedicated
display account, then reboot. The script waits for both local web endpoints
and relaunches a window if Chromium exits. Test the actual screen placement;
adjust the output names in `rc.xml` if the head and body are reversed.

The first time each profile opens, grant camera and microphone permissions
for the head profile as appropriate. The current **Hey FRED** browser feature
still requires a tap after each launch and may use an online speech provider.
Automatic, offline hands-free listening requires a separate local wake-word
and audio service. Use **Tap to speak** only when server transcription is
configured; its audio is sent to the selected transcription provider.

## 4. Boot acceptance check

With no keyboard attached, restart the Pi and check:

1. Head face and body app appear on the correct LCDs without manual launch.
2. Touch controls and camera permission work after the restart.
3. The audio script records from the intended microphone and plays through
   the intended head speakers.
4. FRED completes a spoken turn, with the expected online/offline behavior.
5. A due reminder appears, ACTION acknowledges it, and HELP produces a
   caregiver delivery record. Confirm actual delivery with a test contact.
6. Unplug and reconnect the Pico, then interrupt and restore Wi-Fi. Check
   recovery and `journalctl -u fred -b` for failures.

This is a supervised prototype check, not a release or emergency-service test.
