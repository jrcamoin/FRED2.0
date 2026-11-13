# Compute Module 5 build integration

This is the integration record for the parts acquired from 16 September to
6 October 2026. It identifies what can be assembled and tested now. Exact
part numbers and ratings must be recorded before final power wiring or servo
calibration.

## Parts and intended roles

| Received | Parts | Planned role and check |
|---|---|---|
| 2026-09-16 | Perf board, JST connectors | Prototype low-current signal distribution only until board trace and connector series/current ratings are known. Identify connector polarity and keying on both ends. |
| 2026-09-16 | Raspberry Pi Camera | Head-mounted CSI camera. Record camera model and ribbon type; test through `rpicam-hello --list-cameras`. |
| 2026-09-16 | Raspberry Pi Compute Module 5 and I/O board | Main computer and camera/display carrier. Record the I/O board model: CM5IO and CM4IO have different power inputs. |
| 2026-09-22 | M2.5 heat-set inserts, servos, universal joints, axles, bushings, pins | Neck drive and supports. Record servo model, quantity, stall current, pulse range, torque, horn geometry, and allowed travel. Hand-check the assembled joint with power off. |
| 2026-09-24 | M6 heat-set inserts, cotter pin assortment, washers | Frame fasteners and retained shafts. Confirm material, insert dimensions, load path, washer clearance, and positive retention. |
| 2026-09-26 | M6 × 20 fasteners | Frame assembly. Check thread engagement and interference with wiring and moving parts. |
| 2026-10-06 | 5 V and 6 V voltage regulators, higher-current 12 V supply | Separate, rated power rails after input/output polarity, current, cooling, and connector ratings are verified. |

## Power decision before connecting anything

The **official Compute Module 5 I/O board takes 5 V through USB-C**. Its two
HDMI outputs and two combined camera/display connectors suit the planned two
LCDs plus one CSI camera. The older CM4 I/O board has a 12 V barrel input;
that distinction matters here. **Do not apply the 12 V supply to a CM5IO
USB-C input or GPIO header.** See [Raspberry Pi Compute Module hardware](https://www.raspberrypi.com/documentation/computers/compute-module.html).

Initial bring-up uses a suitable standalone 5 V USB-C supply for the CM5IO.
Keep the new 12 V supply disconnected from the computer. A later integrated
power design may use the 12 V supply as an upstream bus **only after** the
regulators' input ranges, output current, protection, thermal performance, and
the I/O board's power-entry method are confirmed. The proposed branches are:

```text
12 V supply (future, after ratings and protection are verified)
  ├── 5 V regulator → rated 5 V loads, possibly CM5IO via a validated USB-C power path
  └── 6 V regulator → servo power, if the actual servos specify 6 V

Pico PWM signals → servo signal pins (only after calibration)
Pico GND ↔ servo supply GND (shared signal reference)
```

The 5 V and 6 V outputs must not be tied together. Do not use the perf board,
an unidentified JST connector, or thin signal wire as an unverified main
power bus. Size conductors, fuses, connectors, and regulators using measured
peak load and servo **stall** current, not idle current. Check polarity with
a meter before attaching the CM5, Pico, camera, displays, or servos.
The official CM5IO can use a 1.8 V or 3.3 V GPIO reference; check its selected
setting before any direct GPIO connection to the 3.3 V Pico or another part.
The current Pi-to-Pico connection is USB, so it does not require a direct
GPIO signal wire.

## CSI camera bring-up

With all power disconnected, attach the camera to a compatible CAM/DISP port
using the correct 22-pin adapter/ribbon. On the official CM5IO, CAM/DISP1
requires the J6 jumpers shown on the board. Confirm this against the exact
carrier and camera before fitting jumpers. See [Raspberry Pi camera connection](https://www.raspberrypi.com/documentation/accessories/camera.html)
and [Compute Module camera setup](https://www.raspberrypi.com/documentation/computers/compute-module.html).

After boot:

```bash
rpicam-hello --list-cameras
dementia-care-robot hardware-check
```

`/dev/video*` alone is not proof that a CSI camera is usable: Pi systems also
expose codec and ISP nodes. The hardware check now queries `rpicam-hello`.
Only after it identifies the sensor should the head Chromium page be tested
for camera permission and preview. The current head code uses browser
`getUserMedia`; CSI-to-browser exposure still needs validation on the actual
CM5 image. The ROS camera path also needs a compatible camera publisher for
the selected sensor. See [Raspberry Pi camera software](https://www.raspberrypi.com/documentation/computers/camera_software.html).

## Neck assembly and servo bring-up

1. Assemble axles, bushings, universal joints, washers, and retaining pins
   without servos or power. Check full travel by hand for binding, pinch
   points, loose shafts, and cable snagging.
2. Mount one servo and verify its model and rail voltage. Measure current at
   free motion and stall under controlled bench conditions; confirm the 6 V
   regulator and connector ratings cover all servos together.
3. With the horn detached, determine safe center and pulse endpoints. Record
   the mechanical angle limits with the horn and linkage installed.
4. Fill `SERVO_CALIBRATION` in [`firmware/pico/main.py`](../firmware/pico/main.py)
   for both axes. The firmware ships with `SERVO_OUTPUT_ENABLED = False` and
   refuses to enable outputs while calibration fields are missing.
5. Enable one axis at a time at low speed, with a power disconnect within
   reach. Recheck the limits after the full head, camera cable, and LCD loads
   are attached. The current control path commands position but has no
   measured servo feedback or mechanical end-stop sensing.

Do not infer servo voltage, torque, or PWM pulse range from the purchase list;
those depend on the exact model.

## Build record to fill in

| Item | Exact model / rating / measured result |
|---|---|
| I/O board and CM5 RAM/storage variant | Pending |
| Carrier GPIO reference setting | Pending |
| Camera model, cable, and chosen CAM/DISP port | Pending |
| Head and body LCD models, power draw, and audio/USB paths | Pending |
| Servo models, quantity, voltage, stall current, pulse range | Pending |
| 5 V regulator input/output/current rating | Pending |
| 6 V regulator input/output/current rating | Pending |
| 12 V supply rated current and connector polarity | Pending |
| JST connector series, pin count, and current rating | Pending |
| LED ring type/count and measured current | Pending |
| Pico/RP2040 model and serial connection | Pending |

## First powered milestone

Power only the CM5IO from its validated 5 V USB-C supply. Confirm both LCDs,
audio, and the CSI camera. Then connect the Pico over USB with servo output
disabled. Test the HELP and ACTION switches. Add the separate servo rail and
one calibrated actuator only after the power and mechanical records above are
complete. The [Pi startup guide](../deploy/pi5/README.md) covers boot and
audio checks.
