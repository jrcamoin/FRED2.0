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
pan_servo = PWM(Pin(PAN_SERVO_PIN)); tilt_servo = PWM(Pin(TILT_SERVO_PIN))
pan_servo.freq(50); tilt_servo.freq(50)
neck = {"pan": 0.0, "tilt": 0.0, "target_pan": 0.0, "target_tilt": 0.0, "speed": 90.0}

def servo_angle(servo, angle):
    # Standard 500-2500 us pulse range. Calibrate and mechanically limit first.
    pulse_us = 1500 + (angle / 90.0) * 1000
    servo.duty_u16(int(pulse_us * 65535 / 20000))

def update_neck(dt):
    step = neck["speed"] * dt
    for axis, servo in (("pan", pan_servo), ("tilt", tilt_servo)):
        target = neck["target_" + axis]; delta = target - neck[axis]
        neck[axis] += max(-step, min(step, delta))
        servo_angle(servo, neck[axis])


def set_ring(state):
    color = COLORS.get(state, COLORS["alert"])
    scaled = tuple(int(channel * BRIGHTNESS) for channel in color)
    ring.fill(scaled)
    ring.write()


set_ring("idle")
servo_angle(pan_servo, 0); servo_angle(tilt_servo, 0)
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
                neck["speed"] = max(10, min(180, float(command[3])))
            except ValueError:
                pass
    time.sleep_ms(10)
