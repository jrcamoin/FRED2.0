const face = document.getElementById('face');
const video = document.getElementById('camera');
const canvas = document.getElementById('trackingOverlay');
const context = canvas.getContext('2d');
const preview = document.getElementById('trackingPreview');
const toggle = document.getElementById('trackingToggle');
const status = document.getElementById('trackingStatus');
const mode = new URLSearchParams(location.search).get('tracking');
let stream, detector, detectorKind, timer, lastFrame = -1, lastNeck = 0, stopped = false;

toggle.onclick = () => {
  preview.hidden = !preview.hidden;
  toggle.textContent = preview.hidden ? 'Show tracking' : 'Hide tracking';
  toggle.setAttribute('aria-expanded', String(!preview.hidden));
};

function gaze(u = 0, v = 0) {
  face.style.setProperty('--gx', `${u * 30}px`);
  face.style.setProperty('--gy', `${v * 20}px`);
  if (Date.now() - lastNeck > 350) {
    lastNeck = Date.now();
    fetch('/api/neck', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({pan: u * 55, tilt: v * 24, speed: 70})}).catch(() => {});
  }
}

async function loadDetector() {
  if ('FaceDetector' in window) {
    detector = new window.FaceDetector({fastMode: true, maxDetectedFaces: 5});
    detectorKind = 'native';
    return;
  }
  const {FaceDetector, FilesetResolver} = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/vision_bundle.mjs');
  detector = await FaceDetector.createFromOptions(
    await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm'),
    {baseOptions: {modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite'},
      runningMode: 'VIDEO', minDetectionConfidence: 0.6});
  detectorKind = 'mediapipe';
}

function boxes(raw) {
  const found = detectorKind === 'native' ? raw : raw.detections;
  return found.map(d => detectorKind === 'native'
    ? {x: d.boundingBox.x, y: d.boundingBox.y, width: d.boundingBox.width, height: d.boundingBox.height}
    : {x: d.boundingBox.originX, y: d.boundingBox.originY, width: d.boundingBox.width, height: d.boundingBox.height})
    .sort((a, b) => b.width * b.height - a.width * a.height);
}

async function tick() {
  if (stopped) return;
  try {
    if (video.readyState >= 2 && video.currentTime !== lastFrame) {
      lastFrame = video.currentTime;
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      const result = detectorKind === 'native' ? await detector.detect(video) : detector.detectForVideo(video, performance.now());
      const detected = boxes(result);
      context.clearRect(0, 0, canvas.width, canvas.height);
      detected.forEach((box, index) => {
        context.strokeStyle = index === 0 ? '#43ff99' : '#b3bdc6';
        context.lineWidth = index === 0 ? 5 : 2;
        context.strokeRect(box.x, box.y, box.width, box.height);
      });
      if (detected.length) {
        const box = detected[0];
        const u = Math.max(-1, Math.min(1, 2 * (box.x + box.width / 2) / canvas.width - 1));
        const v = Math.max(-1, Math.min(1, 2 * (box.y + box.height / 2) / canvas.height - 1));
        gaze(u, v); status.textContent = `Tracking ${detected.length} face${detected.length === 1 ? '' : 's'}.`;
      } else { gaze(); status.textContent = 'Camera on. No face detected.'; }
    }
  } catch (error) { status.textContent = `Tracking stopped: ${error.message}`; stop(); return; }
  timer = setTimeout(tick, 100);
}

function stop() {
  stopped = true; clearTimeout(timer);
  stream?.getTracks().forEach(track => track.stop());
  video.srcObject = null; detector?.close?.();
  face.style.setProperty('--gx', '0px'); face.style.setProperty('--gy', '0px');
}

async function start() {
  if (!navigator.mediaDevices?.getUserMedia) { status.textContent = 'Camera needs localhost or HTTPS.'; return; }
  try {
    status.textContent = 'Starting camera…';
    stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user', width: {ideal: 640}, height: {ideal: 480}}, audio: false});
    video.srcObject = stream; await video.play();
    status.textContent = 'Camera on. Loading face tracker…';
    await loadDetector();
    if (!stopped) tick();
  } catch (error) { status.textContent = `Tracking unavailable: ${error.message}. Check camera permission and internet access for MediaPipe.`; }
}

if (mode === 'ros') {
  status.textContent = 'ROS tracking mode. Camera preview is unavailable.';
  toggle.hidden = true;
  const script = document.createElement('script'); script.src = '/static/site/hri-gaze.js'; document.body.append(script);
} else if (mode === 'preview') {
  status.textContent = 'Tracking from laptop preview.'; toggle.hidden = true;
  let lastGaze = 0;
  addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== parent || event.data?.type !== 'preview-gaze') return;
    const {u, v} = event.data;
    if (!Number.isFinite(u) || !Number.isFinite(v)) return;
    lastGaze = performance.now();
    face.style.setProperty('--gx', `${Math.max(-1, Math.min(1, u)) * 30}px`);
    face.style.setProperty('--gy', `${Math.max(-1, Math.min(1, v)) * 20}px`);
  });
  setInterval(() => { if (performance.now() - lastGaze > 600) { face.style.setProperty('--gx', '0px'); face.style.setProperty('--gy', '0px'); } }, 200);
} else start();
addEventListener('pagehide', stop);
