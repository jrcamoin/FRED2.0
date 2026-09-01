"""FRED Pico firmware (MicroPython): switches + WS2812/NeoPixel status ring."""

import sys
import time
import uselect
from machine import Pin
from neopixel import NeoPixel

LED_PIN = 16
LED_COUNT = 12
HELP_SWITCH_PIN = 14
ACTION_SWITCH_PIN = 15
BRIGHTNESS = 0.12

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


def set_ring(state):
    color = COLORS.get(state, COLORS["alert"])
    scaled = tuple(int(channel * BRIGHTNESS) for channel in color)
    ring.fill(scaled)
    ring.write()


set_ring("idle")
while True:
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
    time.sleep_ms(10)
