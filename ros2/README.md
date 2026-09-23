# FRED HRI tracking

Three separate `ament_python` ROS 2 processes target Jazzy (Ubuntu 24.04,
Python 3.12) or Humble (Ubuntu 22.04, Python 3.10). They are independent of
the main web application's Python environment. Use 64-bit userspace on Pi 5.
The code has not yet been run on ROS or benchmarked on the physical Pi.

| Topic | Type | Contract |
| --- | --- | --- |
| `/camera/image_raw` | `sensor_msgs/Image` | Unmirrored camera image, capture stamp in shared ROS clock |
| `/perception/gaze_target` | `geometry_msgs/PointStamped` | x right, y down, each −1…1; z unused; original image header |
| `/hardware/neck_targets` | `sensor_msgs/JointState` | `neck_pan`, `neck_tilt`; absolute radians and rad/s; command timestamp |
| `/head_app/digital_gaze` | `geometry_msgs/PointStamped` | x=u, y=v, right/down −1…1; z=1 tracking, z=0 lost; command timestamp |

All topics use volatile, best-effort, keep-last depth 1. Configure the separate
serial subscriber with matching QoS. The neck output is a command, not measured
feedback. The serial node must convert radians to calibrated servo units, enforce
its own limits and stop on missing commands. This package does not open the serial
port; do not run another neck controller concurrently.

## Install and launch

Install your ROS distribution first. From the repository root, in a shell with
`/opt/ros/jazzy/setup.bash` (or Humble) sourced:

```bash
sudo apt install python3-venv python3-colcon-common-extensions python3-rosdep
rosdep install --from-paths ros2/src --ignore-src -r -y
/usr/bin/python3 -m venv --system-site-packages /tmp/fred-hri-env
source /tmp/fred-hri-env/bin/activate
python -m pip install -r ros2/src/fred_hri/requirements.txt
python -c 'import rclpy, cv_bridge, mediapipe; from websockets.asyncio.server import serve'
cd ros2
colcon build --symlink-install
source install/setup.bash
ros2 launch fred_hri tracking.launch.py model_path:=/absolute/path/face_landmarker.task
```

Download the Face Landmarker task model from the official
[MediaPipe model guide](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/index#models).
Model files are deliberately not downloaded at startup. Record the model checksum
and freeze the resolved dependency versions for the deployed image. MediaPipe
wheel availability depends on Python/ARM64 platform; the import check must pass
with the ROS system ABI before building. If no matching wheel is available,
build MediaPipe for that platform or use a validated deployment image. Do not
replace ROS's Python with an unrelated interpreter to force installation.

Run a USB camera ROS driver separately, publishing RGB/BGR images (cv_bridge
converts supported encodings) with accurate timestamps. Start at 640×480, 30 Hz;
use `image_topic:=/your/image_topic` to remap. No images or identity embeddings
are stored or sent to the browser. Face Landmarker detects visible faces; this
is not full-body tracking through occlusions or person re-identification.

Run the existing web server and open
`http://127.0.0.1:8080/head?tracking=ros` on the head. This disables browser
camera acquisition and browser neck commands; emotion polling continues.
The body continues using `/app`. WebSocket JSON is versioned:

```json
{"type":"gaze","version":1,"sequence":42,"u":0.2,"v":-0.1,"tracking":true,"stamp":{"sec":123,"nanosec":0}}
```

The gateway binds loopback:8765 and accepts only the two localhost web origins
by default. Remote displays require an explicitly configured origin and bind
address; HTTPS displays need a TLS WebSocket reverse proxy and a corresponding
client URL change. It is not an authenticated public service.

## Control and latency choices

The dedicated perception executor performs VIDEO-mode inference synchronously;
the DDS depth-one queue keeps only the newest waiting frame. This bounds memory
and preserves the exact source timestamp without asynchronous callback lookup.
Frames older than 200 ms are rejected before and after inference. MediaPipe's
video tracking avoids repeated detector work. See the official
[Face Landmarker Python guide](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python)
and [ROS sensor QoS guidance](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html).

Largest projected face area approximates closest person; it cannot establish
metric distance. Selection can switch when two similarly sized faces cross.
Eye corners supply a stable centroid without needing iris tracking. Maximum
face count defaults to three; lowering it reduces work but changes selection.

The 50 Hz coordinator turns angular camera error into velocity with PID,
filtered derivative, bounded integral, deadband, angular limits, speed limits
and acceleration limits. Digital eyes respond immediately, then compensate
for estimated commanded neck movement between detections. This is an estimate:
servo feedback and camera extrinsic calibration are required for precise
physical synchronization. The camera must be mounted on the moving head.

Configure startup ROS parameters with `--ros-args -p name:=value`: `control_hz`,
`target_timeout_s`, `horizontal_fov_deg`, `vertical_fov_deg`, `pan_sign`,
`tilt_sign`, and each axis's `_limit_deg`, `_kp`, `_ki`, `_kd`, `_max_speed`
(rad/s), `_max_acceleration` (rad/s²), `_deadband` (radians).
Default positive pan is left and positive tilt down; calibrate the serial
mapping and signs on the assembly. Defaults are starting values, not tuned gains.
Targets expire after 250 ms from capture; the neck holds its last commanded
pose and digital gaze centers. The gateway and browser also have independent
stale-stream timeouts. Camera stamps must share the ROS clock; zero, future,
out-of-order and stale targets are rejected. Restart tracking after a ROS clock
reset; offline rosbag simulation is not a supported motion-control mode.

WebSocket delivery runs in a separate asyncio thread. Each client gets a
one-message queue; slow sends time out, and clients are capped at four. There
is no unbounded per-frame task or callback queue. This is low-latency design,
not a hard real-time guarantee or a measured FPS claim.

## Verification

Run portable control tests from the repository root:

```bash
PYTHONPATH=ros2/src/fred_hri python -m unittest discover -s ros2/src/fred_hri/test -v
```

Before release on the actual Pi, exercise camera loss, occlusion, crossing
faces, delayed/out-of-order images, unplugged servos, client reconnection and
both LCDs under simultaneous speech load. Measure capture-to-neck-command and
capture-to-render p50/p95/p99 latency, dropped frames, CPU and temperature;
confirm stable convergence and calibrated travel limits. The local tests cover
control convergence, acceleration/position bounds and target selection, not
ROS transport, MediaPipe inference, browser rendering or hardware performance.
