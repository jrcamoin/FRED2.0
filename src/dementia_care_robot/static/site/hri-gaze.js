// ROS mode owns gaze only. The existing behavior polling still owns emotion.
(() => {
  const face = document.getElementById('face');
  face.querySelector('.eyes').style.transition = 'transform 35ms linear';
  let socket, reconnect, lastMessage = 0;
  function center() {
    face.style.setProperty('--gx', '0px');
    face.style.setProperty('--gy', '0px');
    face.style.setProperty('--px', '0%');
    face.style.setProperty('--py', '0%');
  }
  function connect() {
    socket = new WebSocket(`ws://${location.hostname}:8765`);
    socket.onmessage = event => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== 'gaze' || data.version !== 1 ||
            !Number.isFinite(data.u) || !Number.isFinite(data.v) ||
            Math.abs(data.u) > 1 || Math.abs(data.v) > 1) return;
        lastMessage = performance.now();
        const x = Math.max(-1, Math.min(1, data.u * 1.8));
        const y = Math.max(-1, Math.min(1, data.v * 1.8));
        face.style.setProperty('--gx', `${x * 22}px`);
        face.style.setProperty('--gy', `${y * 14}px`);
        face.style.setProperty('--px', `${x * 80}%`);
        face.style.setProperty('--py', `${y * 65}%`);
      } catch (_) { /* Ignore malformed messages without breaking animation. */ }
    };
    socket.onclose = () => { center(); reconnect = setTimeout(connect, 1000); };
    socket.onerror = () => socket.close();
  }
  const watchdog = setInterval(() => {
    if (performance.now() - lastMessage > 600) center();
  }, 200);
  addEventListener('pagehide', () => {
    clearTimeout(reconnect); clearInterval(watchdog);
    if (socket) { socket.onclose = null; socket.close(); }
  });
  connect();
})();
