// Short, gentle cues accompany happy and sad emotion changes and previews.
(() => {
  let audio;

  function cue(emotion) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    try {
      audio ||= new AudioContext();
      if (audio.state === 'suspended') audio.resume();
      const notes = emotion === 'happy' ? [523, 659, 784] : [392, 349, 294];
      notes.forEach((frequency, index) => {
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        const start = audio.currentTime + index * 0.14;
        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.001, start);
        gain.gain.linearRampToValueAtTime(0.035, start + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.001, start + 0.22);
        oscillator.connect(gain).connect(audio.destination);
        oscillator.start(start);
        oscillator.stop(start + 0.23);
      });
    } catch (_) { /* The expression still works if audio is unavailable. */ }
  }

  window.fredEmotionChanged = emotion => {
    if (emotion === 'happy' || emotion === 'sad') cue(emotion);
  };
  // The first state request can finish before this deferred script loads.
  if (lastState.emotion === 'happy' || lastState.emotion === 'sad') cue(lastState.emotion);
  addEventListener('pagehide', () => { audio?.close(); });
})();
