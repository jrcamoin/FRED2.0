"""FRED Pico firmware (MicroPython): switches + WS2812/NeoPixel status ring."""

import sys
import time
import uselect
from machine import Pin, PWM
from neopixel import NeoPixel

LED_PIN = 16
LED_COUNT = 12
HELP_SWITCH_PIN = 14
ACTION_SWITCH_PIN = 15
BRIGHTNESS = 0.12
PAN_SERVO_PIN = 18
TILT_SERVO_PIN = 19
# Keep new, uncalibrated servos de-energized. Set True only after verifying
# the servo model, power rail, horn orientation, pulse range, and hard stops.
SERVO_OUTPUT_ENABLED = False
SERVO_CALIBRATION = {
    # Fill from the servo datasheet and measured mechanical stops before enabling.
    # Pulse endpoints may be reversed when a servo is mounted in the opposite direction.
    "pan": {"min_deg": None, "max_deg": None, "min_us": None, "center_us": None, "max_us": None},
    "tilt": {"min_deg": None, "max_deg": None, "min_us": None, "center_us": None, "max_us": None},
}

COLORS = {
    "idle": (0, 35, 18),
    "listening": (0, 30, 90),
    "thinking": (65, 35, 0),
    "speaking": (45, 0, 65),
    "alert": (100, 0, 0),
    "off": (0, 0, 0),
}

ring = NeoPixel(Pin(LED_PIN, Pin.OUT), LED_COUNT)
switches = {
    "HELP": Pin(HELP_SWITCH_PIN, Pin.IN, Pin.PULL_UP),
    "ACTION": Pin(ACTION_SWITCH_PIN, Pin.IN, Pin.PULL_UP),
}
previous = {name: pin.value() for name, pin in switches.items()}
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)
if SERVO_OUTPUT_ENABLED:
    for axis in ("pan", "tilt"):
        values = SERVO_CALIBRATION[axis]
        if None in values.values() or not (values["min_deg"] < 0 < values["max_deg"]):
            raise ValueError("Calibrate servo angles and pulses before enabling " + axis)
        pulses = (values["min_us"], values["center_us"], values["max_us"])
        if not (all(500 <= pulse <= 2500 for pulse in pulses) and
                (pulses[0] < pulses[1] < pulses[2] or pulses[0] > pulses[1] > pulses[2])):
            raise ValueError("Invalid servo pulse calibration for " + axis)
pan_servo = PWM(Pin(PAN_SERVO_PIN)) if SERVO_OUTPUT_ENABLED else None
tilt_servo = PWM(Pin(TILT_SERVO_PIN)) if SERVO_OUTPUT_ENABLED else None
if SERVO_OUTPUT_ENABLED:
    pan_servo.freq(50); tilt_servo.freq(50)
neck = {"pan": 0.0, "tilt": 0.0, "target_pan": 0.0, "target_tilt": 0.0, "speed": 90.0}

def servo_angle(servo, axis, angle):
    calibration = SERVO_CALIBRATION[axis]
    angle = max(calibration["min_deg"], min(calibration["max_deg"], angle))
    endpoint = "max" if angle >= 0 else "min"
    pulse_us = calibration["center_us"] + (angle / calibration[endpoint + "_deg"]) * (
        calibration[endpoint + "_us"] - calibration["center_us"])
    servo.duty_u16(int(pulse_us * 65535 / 20000))

def update_neck(dt):
    if not SERVO_OUTPUT_ENABLED:
        return
    step = neck["speed"] * dt
    for axis, servo in (("pan", pan_servo), ("tilt", tilt_servo)):
        target = neck["target_" + axis]; delta = target - neck[axis]
        neck[axis] += max(-step, min(step, delta))
        servo_angle(servo, axis, neck[axis])


def set_ring(state):
    color = COLORS.get(state, COLORS["alert"])
    scaled = tuple(int(channel * BRIGHTNESS) for channel in color)
    ring.fill(scaled)
    ring.write()


set_ring("idle")
if SERVO_OUTPUT_ENABLED:
    servo_angle(pan_servo, "pan", 0); servo_angle(tilt_servo, "tilt", 0)
last_tick = time.ticks_ms()
while True:
    now = time.ticks_ms(); update_neck(time.ticks_diff(now, last_tick) / 1000); last_tick = now
    for name, pin in switches.items():
        current = pin.value()
        if current != previous[name]:
            time.sleep_ms(25)
            current = pin.value()
            if current != previous[name]:
                previous[name] = current
                print("SWITCH", name, "PRESS" if current == 0 else "RELEASE")
    if poll.poll(0):
        command = sys.stdin.readline().strip().split()
        if len(command) == 2 and command[0] == "LED":
            set_ring(command[1])
        elif len(command) == 4 and command[0] == "NECK":
            try:
                neck["target_pan"] = max(-60, min(60, float(command[1])))
                neck["target_tilt"] = max(-25, min(25, float(command[2])))
                if SERVO_OUTPUT_ENABLED:
                    for axis in ("pan", "tilt"):
                        limits = SERVO_CALIBRATION[axis]
                        neck["target_" + axis] = max(limits["min_deg"], min(limits["max_deg"], neck["target_" + axis]))
                neck["speed"] = max(10, min(180, float(command[3])))
            except ValueError:
                pass
    time.sleep_ms(10)
