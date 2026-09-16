"""States shared by future robot behaviors and simulations."""

from enum import Enum


class RobotState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    MOVING = "moving"
    ERROR = "error"
