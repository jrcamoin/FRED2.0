"""Latest-frame Face Landmarker inference, preserving camera capture stamps."""
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import Image
from rclpy.node import Node

from .common import latest_qos, parameter, run
from .control import closest_eyes


class PerceptionNode(Node):
    def __init__(self):
        super().__init__('perception_node')
        model = parameter(self, 'model_path', '')
        if not Path(model).is_file():
            raise ValueError('model_path must name a local face_landmarker.task model')
        self.width = int(parameter(self, 'inference_width', 640))
        self.max_age = float(parameter(self, 'max_frame_age_s', 0.2))
        count = int(parameter(self, 'max_faces', 3))
        if self.width < 64 or self.max_age <= 0 or count < 1:
            raise ValueError('Invalid inference dimensions, age or face count')
        cv2.setNumThreads(1)
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=model),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=count, min_face_detection_confidence=0.6,
            min_face_presence_confidence=0.6, min_tracking_confidence=0.6,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False)
        self.detector = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self.bridge = CvBridge()
        self.last_ms = -1
        self.publisher = self.create_publisher(PointStamped, '/perception/gaze_target', latest_qos())
        self.subscription = self.create_subscription(
            Image, '/camera/image_raw', self.process, latest_qos())
        self.last_warning = 0.0

    def age(self, header):
        stamp = header.stamp.sec + header.stamp.nanosec * 1e-9
        return self.get_clock().now().nanoseconds * 1e-9 - stamp

    def process(self, message):
        # Single-thread executor + DDS depth one: no Python frame queue. While
        # VIDEO inference blocks this dedicated node, DDS replaces old images.
        if not 0 <= self.age(message.header) <= self.max_age:
            return
        try:
            rgb = self.bridge.imgmsg_to_cv2(message, desired_encoding='rgb8')
            if rgb.shape[1] > self.width:
                rgb = cv2.resize(rgb, (self.width, max(1, round(rgb.shape[0] * self.width / rgb.shape[1]))),
                                 interpolation=cv2.INTER_AREA)
            self.last_ms = max(self.last_ms + 1, time.monotonic_ns() // 1_000_000)
            result = self.detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)), self.last_ms)
            target = closest_eyes(result.face_landmarks)
            if target is None or not 0 <= self.age(message.header) <= self.max_age:
                return  # Silence expires the coordinator's target lease.
            output = PointStamped()
            output.header = message.header
            output.point.x, output.point.y = float(target[1]), float(target[2])
            self.publisher.publish(output)
        except (ValueError, RuntimeError, cv2.error, CvBridgeError) as error:
            if time.monotonic() - self.last_warning > 5:
                self.get_logger().error(f'Inference rejected frame: {error}')
                self.last_warning = time.monotonic()

    def destroy_node(self):
        self.detector.close()
        return super().destroy_node()


def main():
    run(PerceptionNode)
