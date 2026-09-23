"""Fixed-rate neck PID with immediate complementary digital saccades."""
import math
import time

from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import JointState
from rclpy.node import Node

from .common import latest_qos, parameter, run
from .control import Axis, clamp


class HRICoordinatorNode(Node):
    def __init__(self):
        super().__init__('hri_coordinator_node')
        self.rate = float(parameter(self, 'control_hz', 50.0))
        self.timeout = float(parameter(self, 'target_timeout_s', 0.25))
        self.fov = [math.radians(float(parameter(self, f'{axis}_fov_deg', value))) / 2
                    for axis, value in [('horizontal', 65.0), ('vertical', 50.0)]]
        self.signs = [float(parameter(self, f'{axis}_sign', value))
                      for axis, value in [('pan', -1.0), ('tilt', 1.0)]]
        self.axes = []
        for name, limit in [('pan', 60.0), ('tilt', 25.0)]:
            axis = Axis(limit=math.radians(float(parameter(self, name + '_limit_deg', limit))))
            for key in ('kp', 'ki', 'kd', 'max_speed', 'max_acceleration', 'deadband'):
                setattr(axis, key, float(parameter(self, name + '_' + key, getattr(axis, key))))
            if not all(math.isfinite(v) and v >= 0 for v in
                       (axis.limit, axis.kp, axis.ki, axis.kd, axis.max_speed, axis.max_acceleration, axis.deadband)) or min(axis.limit, axis.max_speed, axis.max_acceleration) <= 0:
                raise ValueError('Invalid PID or neck limit parameters')
            self.axes.append(axis)
        if not 1 <= self.rate <= 200 or not 0 < self.timeout <= 2 or any(s not in (-1, 1) for s in self.signs) or any(not 0 < f < math.pi/2 for f in self.fov):
            raise ValueError('Invalid control rate, timeout, FOV or axis signs')
        self.target = None
        self.last_stamp = -1
        self.last_tick = time.monotonic()
        self.neck = self.create_publisher(JointState, '/hardware/neck_targets', latest_qos())
        self.eyes = self.create_publisher(PointStamped, '/head_app/digital_gaze', latest_qos())
        self.subscription = self.create_subscription(PointStamped, '/perception/gaze_target', self.receive, latest_qos())
        self.timer = self.create_timer(1 / self.rate, self.tick)

    def receive(self, msg):
        stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        age = (self.get_clock().now().nanoseconds - stamp) * 1e-9
        values = (msg.point.x, msg.point.y)
        if stamp <= self.last_stamp or not 0 <= age < self.timeout or not all(math.isfinite(v) and abs(v) <= 1 for v in values):
            return
        self.last_stamp = stamp
        self.target = (values, time.monotonic() + self.timeout - age, [a.angle for a in self.axes])
        self.publish_eyes(values, True)  # Visual acquisition need not wait for neck timer.

    def publish_eyes(self, values, valid):
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'head_display'
        msg.point.x, msg.point.y = float(values[0]), float(values[1])
        msg.point.z = 1.0 if valid else 0.0
        self.eyes.publish(msg)

    def tick(self):
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now
        valid = self.target is not None and now < self.target[1]
        gaze = [0.0, 0.0]
        if valid:
            values, _, captured_angles = self.target
            for i, axis in enumerate(self.axes):
                # Predict residual error since capture from commanded movement.
                bearing = math.atan(values[i] * math.tan(self.fov[i]))
                residual = bearing - self.signs[i] * (axis.angle - captured_angles[i])
                axis.update(self.signs[i] * residual, dt)
                residual = bearing - self.signs[i] * (axis.angle - captured_angles[i])
                gaze[i] = clamp(math.tan(residual) / math.tan(self.fov[i]), -1., 1.)
        else:
            for axis in self.axes:
                axis.stop()  # Hold pose; never continue chasing a vanished target.
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['neck_pan', 'neck_tilt']
        msg.position = [axis.angle for axis in self.axes]
        msg.velocity = [axis.velocity for axis in self.axes]
        self.neck.publish(msg)
        self.publish_eyes(gaze, valid)


def main():
    run(HRICoordinatorNode)
