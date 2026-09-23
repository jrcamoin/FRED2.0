import rclpy
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


def latest_qos():
    return QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                      reliability=ReliabilityPolicy.BEST_EFFORT)


def parameter(node, name, default):
    return node.declare_parameter(name, default).value


def run(factory):
    rclpy.init()
    node = None
    try:
        node = factory()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
