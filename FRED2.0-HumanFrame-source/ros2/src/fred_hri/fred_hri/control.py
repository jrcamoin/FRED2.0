"""ROS-independent control math. Image coordinates are right/down positive."""
import math
from dataclasses import dataclass


def clamp(value, low, high):
    return max(low, min(high, value))


@dataclass
class Axis:
    """PID image error -> angular velocity -> bounded absolute angle (radians).

    The camera must move with the neck. Actual servo feedback remains the
    hardware controller's responsibility; angle is a commanded pose estimate.
    """
    limit: float
    kp: float = 1.8
    ki: float = 0.08
    kd: float = 0.025
    max_speed: float = 0.7
    max_acceleration: float = 2.0
    deadband: float = 0.025
    angle: float = 0.0
    velocity: float = 0.0
    integral: float = 0.0
    previous: object = None
    derivative: float = 0.0

    def stop(self):
        self.velocity = self.integral = self.derivative = 0.0
        self.previous = None

    def update(self, error, dt):
        dt = clamp(dt, 0.001, 0.1)
        if abs(error) < self.deadband:
            error = 0.0
            self.integral = 0.0
        raw_d = 0.0 if self.previous is None else (error - self.previous) / dt
        self.derivative += dt / (0.08 + dt) * (raw_d - self.derivative)
        self.previous = error
        candidate = clamp(self.integral + error * dt, -0.5, 0.5)
        raw = self.kp * error + self.ki * candidate + self.kd * self.derivative
        outward = self.angle * error > 0 and abs(self.angle) >= self.limit - 1e-6
        if abs(raw) < self.max_speed and not outward:
            self.integral = candidate
        wanted = clamp(raw, -self.max_speed, self.max_speed)
        self.velocity += clamp(wanted - self.velocity,
                               -self.max_acceleration * dt, self.max_acceleration * dt)
        self.angle = clamp(self.angle + self.velocity * dt, -self.limit, self.limit)
        if abs(self.angle) >= self.limit and self.angle * self.velocity > 0:
            self.velocity = 0.0
        return self.angle


def closest_eyes(faces):
    """Largest apparent face is a proximity proxy, not measured depth.

    Average inner/outer eye corners, stable even without iris refinement.
    """
    candidates = []
    for face in faces:
        if len(face) < 387 or not all(math.isfinite(p.x) and math.isfinite(p.y) for p in face):
            continue
        xs, ys = [p.x for p in face], [p.y for p in face]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > 0:
            eyes = [face[i] for i in (33, 133, 362, 263)]
            candidates.append((area, clamp(sum(p.x for p in eyes) / 2 - 1, -1., 1.),
                               clamp(sum(p.y for p in eyes) / 2 - 1, -1., 1.)))
    return max(candidates, default=None)
