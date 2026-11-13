"""Bounded WebSocket fanout; slow clients cannot delay ROS callbacks."""
import asyncio
import json
import math
import threading
import time

from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from .common import latest_qos, parameter, run


class DisplayGatewayNode(Node):
    def __init__(self):
        super().__init__('display_gateway_node')
        self.host = parameter(self, 'host', '127.0.0.1')
        self.port = int(parameter(self, 'port', 8765))
        self.origins = parameter(self, 'allowed_origins', ['http://127.0.0.1:8080', 'http://localhost:8080'])
        self.rate = float(parameter(self, 'broadcast_hz', 60.0))
        self.timeout = float(parameter(self, 'stale_timeout_s', 0.5))
        self.max_clients = int(parameter(self, 'max_clients', 4))
        if not 1 <= self.port <= 65535 or not 1 <= self.rate <= 120 or not 0 < self.timeout <= 5 or not 1 <= self.max_clients <= 32:
            raise ValueError('Invalid gateway parameters')
        self.lock = threading.Lock()
        self.latest = None
        self.sequence = 0
        self.clients = set()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.failure = None
        self.worker = threading.Thread(target=self.thread_main, name='display-websocket', daemon=True)
        self.worker.start()
        if not self.ready.wait(5) or self.failure:
            self.stop.set()
            self.worker.join(timeout=2)
            raise RuntimeError(f'WebSocket startup failed: {self.failure}')
        self.subscription = self.create_subscription(PointStamped, '/head_app/digital_gaze', self.receive, latest_qos())
        self.monitor = self.create_timer(1.0, self.check_worker)

    def check_worker(self):
        if self.failure:
            raise RuntimeError(f'WebSocket worker failed: {self.failure}')

    def receive(self, msg):
        if not all(math.isfinite(v) and abs(v) <= 1 for v in (msg.point.x, msg.point.y)):
            return
        age = self.get_clock().now().nanoseconds * 1e-9 - (msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9)
        if not 0 <= age <= self.timeout:
            return
        with self.lock:
            self.sequence += 1
            self.latest = ({'type': 'gaze', 'version': 1, 'sequence': self.sequence,
                            'u': msg.point.x, 'v': msg.point.y, 'tracking': msg.point.z > 0,
                            'stamp': {'sec': msg.header.stamp.sec, 'nanosec': msg.header.stamp.nanosec}},
                           time.monotonic() + self.timeout - age)

    async def client(self, websocket):
        if len(self.clients) >= self.max_clients:
            await websocket.close(code=1013, reason='Display limit reached')
            return
        queue = asyncio.Queue(maxsize=1)
        self.clients.add(queue)
        try:
            while not self.stop.is_set():
                payload = await queue.get()
                try:
                    await asyncio.wait_for(websocket.send(payload), timeout=0.25)
                except asyncio.TimeoutError:
                    await websocket.close(code=1013, reason='Display too slow')
                    return
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(queue)

    async def server(self):
        async with serve(self.client, self.host, self.port, origins=self.origins,
                         compression=None, max_size=1024, max_queue=1,
                         write_limit=4096, ping_interval=10, ping_timeout=5, close_timeout=1):
            self.ready.set()
            while not self.stop.is_set():
                with self.lock:
                    latest = self.latest
                payload = latest[0] if latest and time.monotonic() < latest[1] else {
                    'type': 'gaze', 'version': 1, 'u': 0.0, 'v': 0.0, 'tracking': False}
                encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False)
                for queue in tuple(self.clients):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(encoded)
                await asyncio.sleep(1 / self.rate)
            # Wake senders so the server context can close every connection.
            for queue in tuple(self.clients):
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait('{}')

    def thread_main(self):
        try:
            asyncio.run(self.server())
        except Exception as error:
            self.failure = error
            self.ready.set()

    def destroy_node(self):
        self.stop.set()
        self.worker.join(timeout=3)
        return super().destroy_node()


def main():
    run(DisplayGatewayNode)
