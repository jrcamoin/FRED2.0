import base64
import html
import json
import mimetypes
import ssl
import threading
import uuid
import webbrowser
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote

from .api_errors import RemoteServiceError
from .adapters import ConsoleCaregiverNotifier, ConsoleSpeaker
from .conversation import ConversationService, OfflineCompanion, OpenAICompatibleModel
from .coordinator import CareCoordinator
from .hardware import PicoBridge
from .models import Assessment, CareProfile, FamiliarMedia, Reminder, RiskLevel
from .scheduler import ReminderScheduler
from .speech import OpenAITranscriber, SpeechNotConfigured
from .storage import SQLiteStore


class RobotApplication:
    def __init__(self, data_dir: Path, pico_device: str | None = None) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = data_dir / "media"
        self.media_dir.mkdir(exist_ok=True)
        self.store = SQLiteStore(data_dir / "robot.db")
        notifier, speaker = ConsoleCaregiverNotifier(), ConsoleSpeaker()
        self.notifier = notifier
        self.scheduler = ReminderScheduler(self.store, CareCoordinator(speaker, notifier))
        model = OpenAICompatibleModel.from_environment() or OfflineCompanion()
        self.generated_responses = isinstance(model, OpenAICompatibleModel)
        self.response_mode = "local" if self.generated_responses and model.endpoint.startswith("http://127.0.0.1:11434") else "openai" if self.generated_responses else "offline"
        self.conversation = ConversationService(self.store, model, notifier)
        self.transcriber = OpenAITranscriber.from_environment()
        self.server_transcription = self.transcriber is not None
        self.pico = PicoBridge(pico_device, self._hardware_event) if pico_device else None
        if self.pico:
            self.pico.start()

    def _hardware_event(self, switch: str, action: str) -> None:
        if switch == "help" and action == "press":
            assessment = Assessment(RiskLevel.URGENT, "The physical help switch was pressed.", "I am alerting your configured support person.")
            self.notifier.notify(assessment)
            self.set_status("alert")

    def set_status(self, state: str) -> None:
        if self.pico:
            self.pico.set_led(state)

    def voice_turn(self, audio: bytes, content_type: str) -> tuple[str, str, str]:
        if self.transcriber is None:
            raise SpeechNotConfigured("Voice transcription is unavailable in offline mode. Please type a message while testing.")
        self.set_status("thinking")
        try:
            transcript = self.transcriber.transcribe(audio, content_type)
            reply, risk = self.conversation.respond(transcript)
            self.set_status("alert" if risk is RiskLevel.URGENT else "speaking")
            return transcript, reply, risk.value
        except Exception:
            self.set_status("alert")
            raise


def _page(app: RobotApplication, notice: str = "") -> bytes:
    reminders = app.store.list_reminders()
    media = app.store.list_media()
    turns = app.store.conversation()
    profile = app.store.care_profile()
    reminder_cards = "".join(
        f'<li><strong>{html.escape(r.message)}</strong><time>{html.escape(r.due_at.astimezone().strftime("%b %d, %I:%M %p"))}</time></li>'
        for r in reminders
    ) or "<li>No upcoming reminders.</li>"
    media_cards = "".join(
        f'<button class="media-card" data-uri="{html.escape(m.uri, quote=True)}" data-title="{html.escape(m.title, quote=True)}" data-description="{html.escape(m.description, quote=True)}" onclick="showMedia(this)">'
        f'<img src="{html.escape(m.uri, quote=True)}" alt="{html.escape(m.description or m.title, quote=True)}"><span>{html.escape(m.title)}</span></button>'
        for m in media
    ) or '<p class="empty">Add a familiar image using a URL, or place image files in the data/media folder.</p>'
    chat = "".join(f'<div class="turn {t.role}"><b>{"You" if t.role == "user" else "Companion"}</b>{html.escape(t.content)}</div>' for t in turns)
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FRED Care Companion</title><style>
:root{{--navy:#17324d;--navy-dark:#10263b;--teal:#16766f;--teal-dark:#105d58;--mint:#e8f5f2;--blue-soft:#edf4fa;--coral:#c74f45;--amber:#f0b44d;--ink:#203142;--muted:#607181;--line:#dce5eb;--surface:#fff;--canvas:#f4f7f9;--shadow:0 12px 34px rgba(25,52,74,.09)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--canvas);color:var(--ink);font:16px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
button,input{{font:inherit}}button,input{{min-height:48px}}button{{cursor:pointer;border:0;border-radius:12px;padding:12px 18px;background:var(--teal);color:#fff;font-weight:750;transition:transform .15s,background .15s,box-shadow .15s}}button:hover{{background:var(--teal-dark);box-shadow:0 5px 14px rgba(16,93,88,.2)}}button:active{{transform:translateY(1px)}}button:focus-visible,input:focus-visible,summary:focus-visible{{outline:4px solid rgba(240,180,77,.55);outline-offset:2px}}button:disabled{{opacity:.55;cursor:wait}}
.topbar{{background:linear-gradient(120deg,var(--navy-dark),var(--navy));color:#fff;border-bottom:4px solid var(--teal)}}.topbar-inner{{max-width:1240px;margin:auto;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;gap:24px}}.brand{{display:flex;align-items:center;gap:14px}}.brand-mark{{width:48px;height:48px;border-radius:15px;display:grid;place-items:center;background:var(--teal);font-size:1.45rem;font-weight:850;letter-spacing:-.05em}}.brand h1{{font-size:1.25rem;margin:0;letter-spacing:-.02em}}.brand p{{margin:1px 0 0;color:#c9d7e2;font-size:.84rem}}.mode-badge{{display:flex;align-items:center;gap:8px;padding:8px 12px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);border-radius:999px;font-size:.82rem;font-weight:700}}.mode-dot{{width:9px;height:9px;border-radius:50%;background:{'#5de0a3' if app.generated_responses else '#f0b44d'};box-shadow:0 0 0 4px rgba(255,255,255,.08)}}
.shell{{max-width:1240px;margin:0 auto;padding:28px;display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,.8fr);gap:24px;align-items:start}}.notice{{grid-column:1/-1;background:#fff7df;border:1px solid #efd597;border-left:5px solid var(--amber);padding:13px 16px;border-radius:12px;font-weight:650}}.card{{background:var(--surface);border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow)}}.card-head{{padding:22px 24px 14px;border-bottom:1px solid var(--line)}}.card-head h2{{margin:0;font-size:1.18rem;letter-spacing:-.015em}}.eyebrow{{margin:0 0 5px;text-transform:uppercase;letter-spacing:.09em;font-size:.71rem;color:var(--teal);font-weight:850}}.card-body{{padding:22px 24px}}.companion{{grid-row:span 2;overflow:hidden}}.companion .card-head{{background:linear-gradient(135deg,var(--blue-soft),#fff)}}.intro{{display:flex;align-items:center;gap:15px}}.avatar{{width:54px;height:54px;border-radius:50%;background:var(--navy);color:#fff;display:grid;place-items:center;font-weight:850;flex:none}}.intro-copy p{{margin:3px 0 0;color:var(--muted)}}
.voice-panel{{background:var(--mint);border:1px solid #c7e5df;border-radius:16px;padding:16px;text-align:center}}#talkButton{{width:100%;min-height:68px;font-size:1.08rem;background:var(--coral);box-shadow:0 7px 18px rgba(199,79,69,.2)}}#talkButton:hover{{background:#ad3f37}}#talkButton.recording{{animation:pulse 1s infinite;background:#a82e26}}@keyframes pulse{{50%{{transform:scale(1.015);box-shadow:0 0 0 9px rgba(199,79,69,.12)}}}}#voiceStatus{{margin:10px 0 0;color:#405d5a;font-size:.9rem;min-height:1.4em}}
.chat{{height:360px;overflow:auto;padding:18px 4px;scrollbar-color:#afbdc7 transparent}}.chat:empty::after{{content:"Start with a simple question, memory, or request for help.";display:block;text-align:center;color:var(--muted);padding:70px 20px}}.turn{{max-width:86%;padding:12px 15px;margin:10px 0;border-radius:16px 16px 16px 4px;background:var(--blue-soft);white-space:pre-wrap}}.turn.user{{margin-left:auto;background:var(--navy);color:#fff;border-radius:16px 16px 4px 16px}}.turn b{{display:block;font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px;opacity:.72}}.message-form{{display:flex;gap:10px;border-top:1px solid var(--line);padding-top:18px}}.message-form label{{flex:1;margin:0}}.message-form label span{{position:absolute;width:1px;height:1px;overflow:hidden}}.message-form input{{height:52px}}.message-form button{{margin:0;min-width:90px}}.conversation-actions{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:14px}}.link-button{{background:transparent;color:var(--muted);padding:6px 0;min-height:auto;font-size:.84rem;font-weight:650}}.link-button:hover{{background:transparent;color:var(--navy);box-shadow:none}}
.side-stack{{display:grid;gap:24px}}.summary-list{{list-style:none;padding:0;margin:0}}.summary-list li{{padding:12px 0;border-bottom:1px solid var(--line)}}.summary-list li:last-child{{border:0}}.summary-list strong{{display:block}}time{{color:var(--muted);font-size:.84rem}}label{{display:block;margin:13px 0 0;font-size:.86rem;font-weight:750;color:#394c5c}}input{{width:100%;margin-top:5px;padding:10px 12px;border:1.5px solid #b9c7d1;border-radius:11px;background:#fff;color:var(--ink)}}input::placeholder{{color:#8796a2}}form>button{{margin-top:15px}}details.card{{overflow:hidden}}details summary{{list-style:none;cursor:pointer;padding:20px 24px;font-weight:800;display:flex;justify-content:space-between;align-items:center}}details summary::-webkit-details-marker{{display:none}}details summary::after{{content:"+";font-size:1.35rem;color:var(--teal)}}details[open] summary{{border-bottom:1px solid var(--line)}}details[open] summary::after{{content:"−"}}.helper,.warning{{font-size:.8rem;color:var(--muted)}}.warning{{padding:10px 12px;background:#fff8e8;border-radius:9px}}
.gallery{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.media-card{{margin:0;padding:0;overflow:hidden;background:#fff;color:var(--ink);border:1px solid var(--line);text-align:left}}.media-card:hover{{background:#fff;box-shadow:0 5px 15px rgba(25,52,74,.12)}}.media-card img{{width:100%;height:120px;object-fit:cover;display:block}}.media-card span{{display:block;padding:9px 11px;font-size:.83rem}}.empty{{grid-column:1/-1;color:var(--muted);font-size:.88rem}}dialog{{width:min(760px,90vw);border:0;border-radius:20px;padding:24px;box-shadow:0 25px 80px rgba(0,0,0,.25)}}dialog::backdrop{{background:rgba(16,38,59,.7)}}dialog img{{max-width:100%;max-height:65vh;border-radius:12px}}dialog button{{float:right;margin:0}}footer{{max-width:1240px;margin:0 auto;padding:0 28px 30px;color:var(--muted);font-size:.78rem;text-align:center}}
@media(max-width:900px){{.shell{{grid-template-columns:1fr}}.companion{{grid-row:auto}}.side-stack{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:650px){{.topbar-inner,.shell{{padding-left:16px;padding-right:16px}}.topbar-inner{{align-items:flex-start;flex-direction:column;gap:12px}}.shell{{padding-top:16px}}.side-stack{{grid-template-columns:1fr}}.card-head,.card-body,details summary{{padding-left:18px;padding-right:18px}}.chat{{height:310px}}.message-form{{flex-direction:column}}.message-form button{{width:100%}}.turn{{max-width:94%}}}}
</style></head><body>
<style>
body{{background:#eef2f6}}.topbar-inner{{max-width:1600px;padding:15px 28px}}.topbar{{border-bottom-width:2px}}.shell{{max-width:1600px;grid-template-columns:minmax(0,1fr) 350px;gap:20px;padding:20px 28px}}.companion{{grid-row:auto;height:calc(100dvh - 155px);min-height:550px;display:flex;flex-direction:column}}.companion>.card-body{{flex:1;min-height:0;display:flex;flex-direction:column;padding:16px 22px}}.chat{{flex:1;height:auto;min-height:100px}}.card-head{{padding:17px 22px}}.side-stack{{gap:16px;max-height:calc(100dvh - 155px);overflow:auto;padding-bottom:4px}}.card{{border-radius:16px;box-shadow:0 3px 16px #17324d08}}.profile{{grid-column:1/-1}}.profile form{{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}}.profile form>button{{justify-self:start}}.voice-panel{{padding:10px 14px;text-align:left}}#talkButton{{min-height:48px;background:var(--teal);box-shadow:none}}#talkButton.recording{{background:#a82e26}}#voiceStatus{{font-size:.82rem}}.voice-panel .helper{{margin:5px 0}}.turn{{overflow-wrap:anywhere}}.conversation-actions{{flex-wrap:wrap}}.tools{{display:flex;align-items:center;flex-wrap:wrap;gap:14px;margin-top:10px}}.tools label{{margin:0;display:flex;gap:6px;align-items:center;font-weight:500}}.tools input{{width:16px;min-height:16px;margin:0}}.suggestions{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0}}.suggestions button{{background:#edf4fa;color:#17324d;font-size:.8rem;min-height:36px;padding:6px 12px;box-shadow:none}}.message-form input{{margin:0}}footer{{padding-bottom:16px}}@media(min-width:1000px) and (max-height:800px){{.intro-copy p:not(.eyebrow){{display:none}}.companion{{min-height:510px}}.card-body{{padding:16px 20px}}}}@media(max-width:900px){{.shell{{grid-template-columns:1fr}}.companion{{height:680px;min-height:0}}.side-stack{{max-height:none;overflow:visible}}}}@media(max-width:650px){{.shell{{padding:12px}}.companion{{height:auto;min-height:640px}}.chat{{height:270px;flex:auto}}.profile form{{grid-template-columns:1fr}}.topbar-inner{{padding:14px 18px}}}}@media(prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
</style>
<header class="topbar"><div class="topbar-inner"><div class="brand"><div class="brand-mark" aria-hidden="true">F</div><div><h1>FRED Care Companion</h1><p>Supportive assistance for everyday moments</p></div></div><div class="mode-badge"><span class="mode-dot"></span>{{"local": "Local AI · no API charges", "openai": "OpenAI configured · connection unverified", "offline": "Offline companion · no API charges"}}[app.response_mode]</div></div></header>
<main class="shell">{f'<div class="notice" role="status">{html.escape(notice)}</div>' if notice else ''}
<section class="card companion" aria-labelledby="companion-title"><div class="card-head"><div class="intro"><div class="avatar" aria-hidden="true">FRED</div><div class="intro-copy"><p class="eyebrow">Patient experience</p><h2 id="companion-title">How can I help today?</h2><p>I can help with familiar routines, misplaced items, or simply listen.</p></div></div></div><div class="card-body">
<div class="voice-panel"><button type="button" id="talkButton" data-server-transcription="{str(app.server_transcription).lower()}">Start speaking</button><p id="voiceStatus" role="status" aria-live="assertive">{"Audio uses configured server transcription." if app.server_transcription else "Voice input uses your browser's speech recognition."}</p>{'' if app.server_transcription else '<p class="helper">No OpenAI transcription charges. Depending on the browser and device, speech may be processed by the browser vendor.</p>'}</div>
<div class="chat" id="chat" aria-live="polite">{chat}</div>
<div class="suggestions" aria-label="Example messages"><button type="button" data-prompt="I need help finding my keys">Find my keys</button><button type="button" data-prompt="What time is it?">Time &amp; date</button><button type="button" data-prompt="What is my routine?">My routine</button></div>
<form class="message-form" id="messageForm" method="post" action="/conversation"><label><span>Message FRED</span><input id="messageInput" name="message" required autocomplete="off" placeholder="Type a question or ask for help…"></label><button>Send</button></form>
<div class="tools"><label><input type="checkbox" id="readAloud" checked>Read replies aloud</label><button class="link-button" id="repeatReply" type="button">Repeat reply</button><button class="link-button" id="stopSpeech" type="button">Stop speaking</button></div>
<div class="conversation-actions"><span class="helper">{"Replies use conversation and profile context." if app.generated_responses else "Offline replies use built-in guidance and your care profile."}</span><form method="post" action="/conversation/clear"><button class="link-button">Clear conversation</button></form></div></div></section>
<aside class="side-stack" aria-label="Caregiver tools">
<section class="card"><div class="card-head"><p class="eyebrow">Care plan</p><h2>Today’s reminders</h2></div><div class="card-body"><ul class="summary-list">{reminder_cards}</ul><details><summary>Add a reminder</summary><form method="post" action="/reminders"><label>Reminder<input name="message" maxlength="200" required placeholder="Time for a glass of water"></label><label>Date and time<input type="datetime-local" name="due_at" required></label><button>Schedule reminder</button></form></details></div></section>
<section class="card"><div class="card-head"><p class="eyebrow">Memory support</p><h2>Familiar photos</h2></div><div class="card-body"><div class="gallery">{media_cards}</div><details><summary>Add a photo</summary><form method="post" action="/media"><label>Photo title<input name="title" maxlength="120" required></label><label>Image URL<input type="url" name="uri" required placeholder="https://…"></label><label>Who or what is pictured?<input name="description" maxlength="300"></label><button>Add familiar photo</button></form></details></div></section>
</aside>
<details class="card profile"><summary>Care profile · personalize assistance</summary><div class="card-body"><p class="helper">Caregiver-provided context helps FRED give familiar and practical answers. Add only consented details that improve care.</p><form method="post" action="/profile">
<label>Preferred name<input name="preferred_name" maxlength="80" value="{html.escape(profile.preferred_name, quote=True)}" placeholder="How FRED should address the person"></label>
<label>Important people<input name="important_people" maxlength="500" value="{html.escape(profile.important_people, quote=True)}" placeholder="Names, relationships, and reassuring contacts"></label>
<label>Interests and favorite activities<input name="interests" maxlength="500" value="{html.escape(profile.interests, quote=True)}" placeholder="Music, hobbies, places, and memories"></label>
<label>Daily routine<input name="daily_routine" maxlength="500" value="{html.escape(profile.daily_routine, quote=True)}" placeholder="Usual meals, activities, and rest times"></label>
<label>Things that provide comfort<input name="comforts" maxlength="500" value="{html.escape(profile.comforts, quote=True)}" placeholder="Calming topics, objects, music, or people"></label>
<label>Usual locations for important items<input name="usual_item_locations" maxlength="500" value="{html.escape(profile.usual_item_locations, quote=True)}" placeholder="Keys: blue bowl by the front door"></label>
<button>Save care profile</button></form><p class="warning">Privacy note: this prototype stores profile data locally without database encryption.</p></div></details>
</main><footer>FRED is an assistive prototype—not a person, clinician, medical device, or emergency service.</footer>
<dialog id="viewer"><button onclick="viewer.close()">Close</button><h2 id="mediaTitle"></h2><img id="mediaImage"><p id="mediaDescription"></p></dialog><script>
const byId = id => document.getElementById(id);
const chat = byId('chat'), talk = byId('talkButton'), status = byId('voiceStatus');
const messageForm = byId('messageForm'), messageInput = byId('messageInput');
const usesServerTranscription = talk.dataset.serverTranscription === 'true';
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
let busy = false, phase = 'idle', recorder, recognition, stream, timer;
let lastReply = '';
const previousReply = chat.querySelector('.turn:not(.user):last-child');
if (previousReply) lastReply = Array.from(previousReply.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('');
function showMedia(card) {{
  byId('mediaTitle').textContent = card.dataset.title;
  byId('mediaImage').src = card.dataset.uri;
  byId('mediaImage').alt = card.dataset.description || card.dataset.title;
  byId('mediaDescription').textContent = card.dataset.description;
  byId('viewer').showModal();
}}
function state(next, text) {{
  phase = next;
  talk.classList.toggle('recording', next === 'recording');
  talk.textContent = next === 'recording' ? 'Stop recording' : next === 'starting' ? 'Opening microphone…' : next === 'processing' ? 'Processing…' : 'Start speaking';
  talk.disabled = next === 'starting' || next === 'processing' || (!usesServerTranscription && !SpeechRecognition);
  talk.setAttribute('aria-pressed', String(next === 'recording'));
  messageForm.querySelector('button').disabled = next !== 'idle';
  if (text) status.textContent = text;
}}
function appendTurn(role, label, text) {{
  const div = document.createElement('div'), b = document.createElement('b');
  div.className = 'turn ' + role; b.textContent = label;
  div.append(b, document.createTextNode(text)); chat.append(div);
  chat.scrollTop = chat.scrollHeight;
}}
function speak(text) {{
  if (!window.speechSynthesis || !text) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = .9; speechSynthesis.speak(utterance);
}}
function replyReceived(data) {{
  lastReply = data.reply;
  appendTurn('assistant', 'FRED', data.reply);
  if (byId('readAloud').checked) speak(data.reply);
  status.textContent = data.risk === 'routine' ? 'Ready for your next message.' : 'Support alert recorded in the server console. No external notification is configured.';
}}
async function request(path, payload) {{
  const response = await fetch(path, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed. Please try again.');
  return data;
}}
messageForm.addEventListener('submit', async event => {{
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text || busy || phase !== 'idle') return;
  busy = true; state('processing', 'Preparing a response…');
  appendTurn('user', 'You', text);
  try {{
    const data = await request('/api/conversation', {{message:text}});
    messageInput.value = ''; replyReceived(data);
  }} catch (error) {{ status.textContent = error.message; }}
  finally {{ busy = false; state('idle'); messageInput.focus(); }}
}});
async function sendAudio(chunks, mime) {{
  clearTimeout(timer); stream?.getTracks().forEach(track => track.stop());
  state('processing', 'Transcribing your recording…'); busy = true;
  try {{
    const blob = new Blob(chunks, {{type:mime}});
    if (!blob.size) throw new Error('No audio captured. Please try again.');
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binary = '';
    for (let i=0; i<bytes.length; i+=8192) binary += String.fromCharCode(...bytes.subarray(i,i+8192));
    const data = await request('/api/voice', {{audio:btoa(binary), content_type:blob.type}});
    appendTurn('user', 'You', data.transcript); replyReceived(data);
  }} catch(error) {{ status.textContent = error.message; }}
  finally {{ busy = false; state('idle'); }}
}}
function stopRecording() {{
  clearTimeout(timer);
  if (phase !== 'recording') return;
  state('processing', 'Finishing recording…');
  if (usesServerTranscription) recorder.stop();
  else recognition.stop();
}}
talk.addEventListener('click', async () => {{
  if (phase === 'recording') {{ stopRecording(); return; }}
  if (phase !== 'idle' || busy) return;
  window.speechSynthesis?.cancel();
  state('starting', 'Allow microphone access if prompted.');
  try {{
    if (usesServerTranscription) {{
      stream = await navigator.mediaDevices.getUserMedia({{audio:true}});
      const chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = event => {{ if (event.data.size) chunks.push(event.data); }};
      recorder.onstop = () => sendAudio(chunks, recorder.mimeType || 'audio/webm');
      recorder.onerror = () => {{ clearTimeout(timer); stream.getTracks().forEach(t => t.stop()); state('idle', 'Recording failed. Please try again.'); }};
      recorder.start();
    }} else {{
      let transcript = '', failure = '';
      recognition = new SpeechRecognition();
      recognition.lang = navigator.language || 'en-US';
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.onresult = event => {{
        transcript = Array.from(event.results).map(result => result[0].transcript).join(' ').trim();
        status.textContent = 'Heard: ' + transcript;
      }};
      recognition.onerror = event => {{
        failure = event.error === 'not-allowed' ? 'Microphone access denied. Enable it in browser settings.' :
          event.error === 'network' ? 'Browser speech recognition needs a network connection. You can still type below.' :
          'Speech recognition could not finish (' + event.error + '). Please try again.';
      }};
      recognition.onend = () => {{
        clearTimeout(timer); state('idle');
        if (transcript && !failure) {{
          messageInput.value = transcript;
          status.textContent = 'Check the transcript below, then press Send.';
          messageInput.focus();
        }} else status.textContent = failure || 'No speech detected. Try again or type below.';
      }};
      recognition.start();
    }}
    state('recording', 'Listening. Click Stop recording when finished.');
    timer = setTimeout(stopRecording, 60000);
  }} catch(error) {{
    stream?.getTracks().forEach(track => track.stop());
    state('idle', 'Microphone unavailable. Check browser permissions or type below.');
  }}
}});
byId('repeatReply').addEventListener('click', () => {{ if (lastReply) speak(lastReply); else status.textContent = 'Send a message first to hear a reply.'; }});
byId('stopSpeech').addEventListener('click', () => window.speechSynthesis?.cancel());
document.querySelector('form[action="/conversation/clear"]').addEventListener('submit', event => {{
  if (!confirm('Delete this conversation? Your care profile will be kept.')) event.preventDefault();
}});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {{
  messageInput.value = button.dataset.prompt; messageInput.focus();
}}));
chat.scrollTop = chat.scrollHeight;
state('idle', !usesServerTranscription && !SpeechRecognition ?
  'Speech recognition is unavailable in this browser. Please type below.' :
  'Click Start speaking to record, or type a message below.');
</script></body></html>"""
    return document.encode()


def make_handler(app: RobotApplication):
    class Handler(BaseHTTPRequestHandler):
        def _redirect(self, notice: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/?notice=" + quote(notice))
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                app.scheduler.deliver_due()
                notice = parse_qs(parsed.query).get("notice", [""])[0]
                body = _page(app, notice)
                self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            if parsed.path.startswith("/local-media/"):
                name = Path(parsed.path).name
                path = app.media_dir / name
                if path.is_file():
                    body = path.read_bytes(); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream"); self.end_headers(); self.wfile.write(body); return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            declared_length = int(self.headers.get("Content-Length", "0"))
            if self.path == "/api/conversation":
                if not 0 < declared_length <= 16384:
                    self._json({"error": "Message is too large or empty."}, HTTPStatus.BAD_REQUEST); return
                try:
                    payload = json.loads(self.rfile.read(declared_length))
                    message = payload.get("message") if isinstance(payload, dict) else None
                    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
                        raise ValueError("Enter a message of 1–2000 characters.")
                    reply, risk = app.conversation.respond(message.strip())
                    self._json({"reply": reply, "risk": risk.value}); return
                except (ValueError, UnicodeError):
                    self._json({"error": "Enter a valid message of 1–2000 characters."}, HTTPStatus.BAD_REQUEST); return
                except RemoteServiceError as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_GATEWAY); return
            if self.path == "/api/voice":
                if declared_length > 12_000_000:
                    self._json({"error": "Recording is too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE); return
                try:
                    payload = json.loads(self.rfile.read(declared_length))
                    audio = base64.b64decode(payload["audio"], validate=True)
                    transcript, reply, risk = app.voice_turn(audio, str(payload.get("content_type", "audio/webm")))
                    self._json({"transcript": transcript, "reply": reply, "risk": risk}); return
                except SpeechNotConfigured as error:
                    self._json({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE); return
                except RemoteServiceError as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_GATEWAY); return
                except (KeyError, ValueError, json.JSONDecodeError) as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST); return
                except Exception as error:
                    print("VOICE ERROR:", repr(error))
                    self._json({"error": "Speech processing failed. Please try again or type a message."}, HTTPStatus.BAD_GATEWAY); return
            if self.path == "/api/status":
                try:
                    payload = json.loads(self.rfile.read(min(declared_length, 1024)))
                    app.set_status(str(payload["state"]))
                    self._json({"ok": True}); return
                except (KeyError, ValueError, json.JSONDecodeError) as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST); return
            length = min(declared_length, 16_384)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()}
            try:
                if self.path == "/reminders":
                    local = datetime.fromisoformat(form["due_at"]).astimezone()
                    app.scheduler.schedule(Reminder(uuid.uuid4().hex, form["message"].strip(), local))
                    self._redirect("Reminder scheduled"); return
                if self.path == "/media":
                    uri = form["uri"].strip()
                    if urlparse(uri).scheme not in ("http", "https"):
                        raise ValueError("Image URL must use http or https")
                    app.store.add_media(FamiliarMedia(uuid.uuid4().hex, form["title"].strip(), uri, "image", form.get("description", "").strip()))
                    self._redirect("Familiar photo added"); return
                if self.path == "/conversation":
                    _, risk = app.conversation.respond(form["message"])
                    self._redirect("Support person notified" if risk != "routine" else "Response ready"); return
                if self.path == "/profile":
                    fields = ("preferred_name", "important_people", "interests", "daily_routine", "comforts", "usual_item_locations")
                    app.store.save_care_profile(CareProfile(*(form.get(field, "").strip() for field in fields)))
                    self._redirect("Care profile saved"); return
                if self.path == "/conversation/clear":
                    app.store.clear_conversation(); self._redirect("Conversation cleared"); return
            except (KeyError, ValueError) as error:
                self.send_error(HTTPStatus.BAD_REQUEST, str(error)); return
            except RemoteServiceError as error:
                print("CONVERSATION ERROR:", repr(error))
                self._redirect(str(error)); return
            self.send_error(HTTPStatus.NOT_FOUND)

        def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            print("WEB:", format % args)
    return Handler


def serve(data_dir: str = "data", host: str = "127.0.0.1", port: int = 8080, open_browser: bool = False, certfile: str | None = None, keyfile: str | None = None, pico_device: str | None = None) -> None:
    app = RobotApplication(Path(data_dir), pico_device)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    if certfile and keyfile:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile, keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    stop = threading.Event()
    def scheduler_loop() -> None:
        while not stop.wait(1):
            app.scheduler.deliver_due()
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    if open_browser:
        scheme = "https" if certfile else "http"
        threading.Timer(0.5, lambda: webbrowser.open(f"{scheme}://{host}:{port}")).start()
    scheme = "https" if certfile else "http"
    print(f"Care Companion running at {scheme}://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if app.pico:
            app.pico.close()
        server.server_close()
