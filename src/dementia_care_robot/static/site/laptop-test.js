const video = document.getElementById('preview');
const canvas = document.getElementById('overlay'), ctx = canvas.getContext('2d');
const toggle = document.getElementById('cameraToggle'), status = document.getElementById('trackingStatus');
const metrics = document.getElementById('metrics'), head = document.getElementById('headPreview');
let detector, stream, active = false, timer, previousTime = -1, generation = 0;
function gaze(u = 0, v = 0) {
  head.contentWindow.postMessage({type: 'preview-gaze', u, v}, location.origin);
}
function stop() {
  generation++; active = false; clearTimeout(timer);
  stream?.getTracks().forEach(track => track.stop()); stream = null; video.srcObject = null;
  ctx.clearRect(0, 0, canvas.width, canvas.height); gaze();
  toggle.textContent = 'Start camera'; toggle.disabled = false;
  status.textContent = 'Camera off.'; metrics.textContent = 'No target';
}
toggle.onclick = async () => {
  if (active) { stop(); return; }
  const token = ++generation;
  toggle.disabled = true; status.textContent = 'Loading face detector and requesting camera permission…';
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw Error('Camera access requires localhost or HTTPS.');
    if (!detector) {
      const {FaceDetector, FilesetResolver} = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/vision_bundle.mjs');
      detector = await FaceDetector.createFromOptions(
        await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm'),
        {baseOptions: {modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite'},
          runningMode: 'VIDEO', minDetectionConfidence: 0.6});
    }
    if (token !== generation) return;
    const acquired = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 640}, height: {ideal: 480}}, audio: false});
    if (token !== generation) { acquired.getTracks().forEach(t => t.stop()); return; }
    stream = acquired; video.srcObject = stream; await video.play();
    if (token !== generation) return;
    active = true; previousTime = -1; toggle.textContent = 'Stop camera';
    tick();
  } catch (error) { stop(); status.textContent = `Camera unavailable: ${error.message}. Check permissions and network access, then retry.`; }
  finally { toggle.disabled = false; }
};
function tick() {
  if (!active) return;
  try {
    if (video.readyState >= 2 && video.currentTime !== previousTime) {
      previousTime = video.currentTime;
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.parentElement.style.aspectRatio = `${canvas.width}/${canvas.height}`;
      const started = performance.now();
      const {detections} = detector.detectForVideo(video, started);
      const elapsed = performance.now() - started;
      const ordered = [...detections].filter(d => d.boundingBox).sort((a,b) =>
        b.boundingBox.width * b.boundingBox.height - a.boundingBox.width * a.boundingBox.height);
      ordered.forEach((d, index) => {
        const b = d.boundingBox; ctx.strokeStyle = index === 0 ? '#43ff99' : '#b3bdc6';
        ctx.lineWidth = index === 0 ? 4 : 2; ctx.strokeRect(b.originX, b.originY, b.width, b.height);
        ctx.fillStyle = ctx.strokeStyle; ctx.font = 'bold 18px system-ui';
        ctx.fillText(index === 0 ? 'TRACKING' : 'Face', b.originX, Math.max(20, b.originY - 8));
      });
      if (ordered.length) {
        const eyes = ordered[0].keypoints.slice(0, 2);
        const x = (eyes[0].x + eyes[1].x) / 2, y = (eyes[0].y + eyes[1].y) / 2;
        const u = Math.max(-1, Math.min(1, 2*x-1)), v = Math.max(-1, Math.min(1, 2*y-1));
        ctx.beginPath(); ctx.arc(x*canvas.width, y*canvas.height, 7, 0, Math.PI*2); ctx.fillStyle='#43ff99'; ctx.fill();
        gaze(u, v); status.textContent = 'Tracking the largest visible face.';
        metrics.textContent = `${ordered.length} face(s) · gaze (${u.toFixed(2)}, ${v.toFixed(2)}) · inference ${elapsed.toFixed(0)} ms`;
      } else { gaze(); status.textContent = 'No face detected. Look toward the camera.'; metrics.textContent = 'No target'; }
    }
    timer = setTimeout(tick, 66); // Bound inference rate; never queue frames.
  } catch (error) { stop(); status.textContent = `Tracking stopped: ${error.message}`; }
}
addEventListener('pagehide', () => { stop(); detector?.close(); });
document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
