// Browser speech recognition prototype; not an offline keyword engine.
function fredWakeCommand(text) {
  const match = /\b(?:hey\s+)?fred\b[\s,.!?:;-]*/i.exec(text);
  return match ? text.slice(match.index + match[0].length).trim() : null;
}
if (typeof module !== 'undefined') module.exports = {fredWakeCommand};
if (typeof document !== 'undefined' && document.getElementById('wakeToggle') && !document.getElementById('talkButton')) (() => {
  const toggle = document.getElementById('wakeToggle'), status = document.getElementById('wakeStatus');
  const reply = document.getElementById('wakeReply');
  const recordButton = document.getElementById('headRecord');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let enabled = false, recognition, armed = false, words = '', timer, restart, busy = false;
  let recorder, stream;
  const hardware = state => fetch('/api/status', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({state})}).catch(() => {});
  function stopListening() {
    clearTimeout(restart); clearTimeout(timer);
    if (recognition) { const old = recognition; recognition = null; old.onend = null; old.abort(); }
  }
  function speak(text) {
    if (!window.speechSynthesis) return Promise.reject(Error('Speech playback is unavailable in this browser'));
    return new Promise((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(text);
      const timeout = setTimeout(() => { window.speechSynthesis.cancel(); reject(Error('Speech playback timed out')); }, 30000);
      utterance.onend = () => { clearTimeout(timeout); resolve(); };
      utterance.onerror = () => { clearTimeout(timeout); reject(Error('Speech playback failed')); };
      window.speechSynthesis.cancel(); window.speechSynthesis.speak(utterance);
    });
  }
  function listen() {
    if (!enabled || busy || recognition) return;
    const current = new Recognition(); recognition = current;
    current.lang = navigator.language || 'en-US'; current.continuous = true; current.interimResults = false;
    current.onresult = event => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (!event.results[i].isFinal) continue;
        const heard = event.results[i][0].transcript.trim();
        if (!armed) {
          const command = fredWakeCommand(heard);
          if (command === null) continue;
          armed = true; words = command; hardware('listening');
        } else words += ' ' + heard;
        status.textContent = words.trim() ? `Heard: ${words.trim()}` : 'I’m listening. Ask your question…';
        clearTimeout(timer); timer = setTimeout(submit, words.trim() ? 1400 : 10000);
      }
    };
    current.onerror = event => {
      if (recognition !== current || event.error === 'aborted' || event.error === 'no-speech') return;
      enabled = false; stopListening(); hardware('idle'); toggle.textContent = 'Enable Hey FRED';
      status.textContent = event.error === 'network'
        ? 'Browser speech recognition is unavailable. Use Tap to speak.'
        : `Microphone error: ${event.error}. Check permission or use Tap to speak.`;
    };
    current.onend = () => { if (recognition === current) { recognition = null; if (enabled && !busy) restart = setTimeout(listen, 500); } };
    try { current.start(); } catch (error) { enabled = false; recognition = null; status.textContent = `Microphone unavailable: ${error.message}`; }
  }
  async function submit() {
    const message = words.trim(); armed = false; words = '';
    if (!enabled || busy) return;
    if (!message) { status.textContent = 'Say “Hey FRED” to try again.'; hardware('idle'); return; }
    busy = true; stopListening(); status.textContent = 'Thinking…'; hardware('listening');
    try {
      const response = await fetch('/api/conversation', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message})});
      const data = await response.json(); if (!response.ok) throw Error(data.error || 'Conversation failed.');
      reply.textContent = data.reply; status.textContent = 'FRED is speaking…';
      await speak(data.reply);
      status.textContent = 'Listening for “Hey FRED”…';
    } catch (error) { status.textContent = `FRED could not respond: ${error.message}`; }
    finally { busy = false; hardware('idle'); if (enabled) restart = setTimeout(listen, 700); }
  }
  toggle.onclick = () => {
    if (enabled) { enabled = false; stopListening(); window.speechSynthesis?.cancel(); hardware('idle'); toggle.textContent = 'Enable Hey FRED'; status.textContent = 'Hands-free off.'; return; }
    if (!Recognition) { status.textContent = 'Speech recognition is unavailable in this browser.'; return; }
    enabled = true; toggle.textContent = 'Turn Hey FRED off'; status.textContent = 'Listening for “Hey FRED”…'; listen();
  };
  if (recordButton) recordButton.onclick = async () => {
    if (recorder?.state === 'recording') { recorder.stop(); recordButton.textContent = 'Tap to speak'; recordButton.disabled = true; status.textContent = 'Transcribing…'; return; }
    if (busy) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { status.textContent = 'Recording is unavailable in this browser.'; return; }
    enabled = false; stopListening(); toggle.textContent = 'Enable Hey FRED';
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:true});
      const chunks = []; recorder = new MediaRecorder(stream);
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop()); stream = null;
        try {
          if (!chunks.length) throw Error('No audio was recorded');
          const blob = new Blob(chunks, {type:recorder.mimeType || 'audio/webm'});
          const bytes = new Uint8Array(await blob.arrayBuffer()); let binary = '';
          for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
          const response = await fetch('/api/voice', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({audio:btoa(binary), content_type:blob.type})});
          const data = await response.json(); if (!response.ok) throw Error(data.error || 'Transcription failed');
          reply.textContent = data.reply; status.textContent = `Heard: ${data.transcript}. FRED is speaking…`;
          await speak(data.reply);
          status.textContent = 'Tap to speak when ready.';
        } catch (error) { status.textContent = `Tap to speak failed: ${error.message}`; }
        finally { busy = false; recordButton.disabled = false; hardware('idle'); }
      };
      recorder.onerror = () => { status.textContent = 'Recording failed. Tap to retry.'; };
      recorder.start(); busy = true; hardware('listening');
      recordButton.textContent = 'Stop speaking'; status.textContent = 'Listening… tap Stop speaking when done.';
    } catch (error) { stream?.getTracks().forEach(track => track.stop()); stream = null; status.textContent = `Microphone access failed: ${error.message}`; }
  };
  addEventListener('pagehide', () => { enabled = false; stopListening(); if (recorder?.state === 'recording') { recorder.onstop = null; recorder.stop(); } stream?.getTracks().forEach(track => track.stop()); });
})();
if (typeof document !== 'undefined') (() => {
  const manual = document.getElementById('talkButton');
  if (!manual) return;
  const panel = document.createElement('section');
  panel.innerHTML = '<button type="button" id="wakeToggle">Enable hands-free · Hey FRED</button><p id="wakeStatus" role="status">Hands-free off.</p><p class="muted">When enabled, your microphone listens for “Hey FRED”. Browser speech recognition may send audio to its provider, including speech before the wake phrase. Turn it off any time. Only your request after the name is sent to FRED’s conversation service.</p>';
  manual.before(panel);
  const toggle = panel.querySelector('button'), status = panel.querySelector('[role=status]');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const form = document.getElementById('messageForm');
  let enabled = false, busy = false, recognition, restart, silence, deadline, speechTimer;
  let armed = false, words = '', version = 0, request, manualDisabled;
  function hardware(state) {
    return fetch('/api/status', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({state})}).catch(()=>{});
  }
  function resetTurn() { armed = false; words = ''; clearTimeout(silence); clearTimeout(deadline); }
  function haltRecognition() {
    clearTimeout(restart);
    if (recognition) { const old = recognition; recognition = null; old.onend = null; old.abort(); }
  }
  function disable(message = 'Hands-free off.') {
    enabled = false; version++; haltRecognition(); resetTurn(); clearTimeout(speechTimer);
    request?.abort(); window.speechSynthesis?.cancel(); busy = false;
    toggle.textContent = 'Enable hands-free · Hey FRED'; status.textContent = message;
    manual.disabled = manualDisabled ?? manual.disabled;
    form.querySelectorAll('input,button').forEach(el => el.disabled = false);
    hardware('idle');
  }
  function add(role, text) {
    const chat = document.getElementById('chat'); chat.querySelector('.chat-empty')?.remove();
    const entry = document.createElement('div'); entry.className = 'turn '+role; entry.textContent = text;
    chat.append(entry); chat.scrollTop = chat.scrollHeight;
  }
  async function submit() {
    if (!enabled || busy) return;
    const message = words.trim(); resetTurn();
    if (!message) { status.textContent = 'No question heard. Say “Hey FRED” to try again.'; hardware('idle'); return; }
    busy = true; haltRecognition(); const token = version;
    status.textContent = 'Thinking…'; add('user', message);
    request = new AbortController(); const timeout = setTimeout(() => request.abort(), 90000);
    try {
      const response = await fetch('/api/conversation', {method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({message}), signal:request.signal});
      const data = await response.json(); if (!response.ok) throw Error(data.error || 'Conversation failed.');
      if (!enabled || token !== version) return;
      add('assistant', data.reply); status.textContent = 'FRED is speaking…';
      const finish = () => {
        if (!enabled || token !== version || !busy) return;
        clearTimeout(speechTimer); busy = false; hardware('idle');
        status.textContent = 'Listening for “Hey FRED”…'; restart = setTimeout(listen, 700);
      };
      if (!window.speechSynthesis) { finish(); return; }
      const utterance = new SpeechSynthesisUtterance(data.reply);
      utterance.onend = finish;
      utterance.onerror = () => { finish(); status.textContent = 'Speech playback failed. Reply is shown above.'; };
      // Never reopen recognition while audio could still be playing.
      speechTimer = setTimeout(() => { window.speechSynthesis.cancel(); finish(); }, 120000);
      window.speechSynthesis.speak(utterance);
    } catch (error) {
      if (enabled && token === version) disable(`Hands-free stopped: ${error.message}. Enable it to retry.`);
    } finally { clearTimeout(timeout); }
  }
  function listen() {
    if (!enabled || busy || recognition) return;
    const current = new Recognition(); recognition = current;
    current.lang = navigator.language || 'en-US'; current.continuous = true; current.interimResults = true;
    current.onresult = event => {
      if (!enabled || busy || recognition !== current) return;
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (!event.results[i].isFinal) { if (armed && words) { clearTimeout(silence); silence=setTimeout(submit,1800); } continue; }
        const text = event.results[i][0].transcript.trim();
        if (!armed) {
          const command = fredWakeCommand(text); if (command === null) continue;
          armed = true; words = command; hardware('listening');
          status.textContent = 'I’m listening. Ask your question…';
          deadline = setTimeout(submit, 15000);
        } else { words += ' ' + text; }
        if (words.trim()) { status.textContent = `Heard: ${words.trim()}`; clearTimeout(silence); silence = setTimeout(submit, 1400); }
      }
    };
    current.onerror = event => {
      if (recognition !== current) return;
      if (event.error !== 'no-speech' && event.error !== 'aborted')
        disable(`Speech recognition unavailable (${event.error}). Check microphone permission or type your message.`);
    };
    current.onend = () => { if (recognition === current) { recognition = null; if (enabled && !busy) restart = setTimeout(listen, 500); } };
    try { current.start(); } catch (error) { disable(`Could not start listening: ${error.message}`); }
  }
  toggle.onclick = () => {
    if (enabled) { disable(); return; }
    if (!Recognition) { status.textContent = 'This browser does not support speech recognition. Try Chrome or use the speak button.'; return; }
    // Avoid overlapping with an existing manual conversation or recording.
    if (manual.textContent === 'Stop speaking' || window.speechSynthesis?.speaking || form.querySelector('button').disabled) {
      status.textContent = 'Finish the current recording or reply before enabling hands-free.'; return;
    }
    enabled = true; version++; manualDisabled = manual.disabled; manual.disabled = true;
    form.querySelectorAll('input,button').forEach(el => el.disabled = true);
    toggle.textContent = 'Turn hands-free off'; status.textContent = 'Listening for “Hey FRED”…'; listen();
  };
  addEventListener('pagehide', () => { if (enabled) disable(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && enabled) disable('Hands-free paused because this page was hidden. Enable it to resume.'); });
})();
