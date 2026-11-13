// HumanFrame Runtime microphone, activated explicitly by the resident.
// Browser speech capture / Hey FRED remain separate existing features.
(() => {
  const button = document.getElementById('robotMicButton');
  const status = document.getElementById('robotMicStatus');
  const chat = document.getElementById('chat');
  if (!button || !status || !chat) return;

  const addTurn = (role, content) => {
    chat.querySelector('.chat-empty')?.remove();
    const item = document.createElement('div');
    item.className = `turn ${role}`;
    const label = document.createElement('b');
    label.textContent = role === 'user' ? 'You' : 'FRED';
    item.append(label, document.createElement('br'), document.createTextNode(content));
    chat.append(item);
    chat.scrollTop = chat.scrollHeight;
  };

  button.addEventListener('click', async () => {
    button.disabled = true;
    status.textContent = 'Recording from the robot microphone for 3 seconds…';
    try {
      const response = await fetch('/api/humanframe/voice', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({duration: 3}),
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Unable to use the robot microphone');
      addTurn('user', data.transcript);
      addTurn('assistant', data.reply);
      status.textContent = 'FRED has responded. You can record again.';
      if (window.speechSynthesis && data.reply) {
        const utterance = new SpeechSynthesisUtterance(data.reply);
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      }
    } catch (error) {
      status.textContent = `Robot microphone unavailable: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
})();
