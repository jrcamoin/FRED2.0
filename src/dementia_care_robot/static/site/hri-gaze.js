// ROS mode owns gaze only. The existing behavior polling still owns emotion.
(() => {
  const face = document.getElementById('face');
  face.querySelector('.eyes').style.transition = 'transform 35ms linear';
  let socket, reconnect, lastMessage = 0;
  function center() {
    face.style.setProperty('--gx', '0px');
    face.style.setProperty('--gy', '0px');
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
        face.style.setProperty('--gx', `${data.u * 30}px`);
        face.style.setProperty('--gy', `${data.v * 20}px`);
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
