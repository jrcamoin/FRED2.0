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
from urllib.parse import parse_qs, urlparse

from .adapters import ConsoleCaregiverNotifier, ConsoleSpeaker
from .conversation import ConversationService, OfflineCompanion, OpenAICompatibleModel
from .coordinator import CareCoordinator
from .hardware import PicoBridge
from .models import Assessment, FamiliarMedia, Reminder, RiskLevel
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
        self.conversation = ConversationService(self.store, model, notifier)
        self.transcriber = OpenAITranscriber.from_environment()
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
            raise SpeechNotConfigured("Voice input requires ROBOT_LLM_API_KEY on the server")
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
<title>Care Companion</title><style>
:root{{--ink:#20302d;--paper:#f7f3e8;--card:#fffdf8;--teal:#276b63;--gold:#e4ad4d}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:18px/1.5 system-ui,sans-serif}}header{{background:var(--teal);color:white;padding:20px 5vw;display:flex;justify-content:space-between;align-items:center}}header h1{{margin:0;font-size:clamp(1.5rem,4vw,2.3rem)}}header span{{font-size:.9rem}}main{{max-width:1200px;margin:auto;padding:28px 5vw;display:grid;gap:24px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}section{{background:var(--card);padding:24px;border-radius:18px;box-shadow:0 4px 18px #243b3520}}h2{{margin-top:0}}label{{display:block;font-weight:650;margin-top:12px}}input,button{{font:inherit}}input{{width:100%;padding:12px;border:2px solid #9aa9a5;border-radius:9px}}button{{cursor:pointer;border:0;border-radius:10px;padding:12px 18px;background:var(--teal);color:white;font-weight:700;margin-top:14px}}button:focus,input:focus{{outline:4px solid var(--gold);outline-offset:2px}}button:disabled{{opacity:.55}}#talkButton{{width:100%;min-height:76px;font-size:1.25rem;background:#9b3d34}}#talkButton.recording{{animation:pulse 1s infinite;background:#c3291d}}@keyframes pulse{{50%{{transform:scale(1.02)}}}}#voiceStatus{{min-height:1.5em;font-weight:650}}ul{{padding:0;list-style:none}}li{{border-bottom:1px solid #ddd;padding:11px 0}}time{{display:block;color:#52645f}}.gallery{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.media-card{{margin:0;padding:0;overflow:hidden;background:#eee;color:var(--ink)}}.media-card img{{width:100%;height:140px;object-fit:cover;display:block}}.media-card span{{display:block;padding:9px}}.chat{{max-height:330px;overflow:auto}}.turn{{padding:12px;margin:8px 0;border-radius:12px;background:#e6efed}}.turn.user{{background:#f6e7c8}}.turn b{{display:block;font-size:.8rem}}.notice{{grid-column:1/-1;background:#fff2c8;padding:12px;border-radius:10px}}dialog{{max-width:800px;border:0;border-radius:18px;padding:20px}}dialog img{{max-width:100%;max-height:65vh}}.warning{{font-size:.85rem;color:#5e5140}}@media(max-width:500px){{main{{padding:15px}}section{{padding:18px}}}}
</style></head><body><header><h1>Care Companion</h1><span>I am a robot assistant</span></header><main>
{f'<div class="notice" role="status">{html.escape(notice)}</div>' if notice else ''}
<section><h2>Today’s reminders</h2><ul>{reminder_cards}</ul><form method="post" action="/reminders"><label>Reminder<input name="message" maxlength="200" required placeholder="Time for a glass of water"></label><label>Date and time<input type="datetime-local" name="due_at" required></label><button>Schedule reminder</button></form></section>
<section><h2>Familiar photos</h2><div class="gallery">{media_cards}</div><form method="post" action="/media"><label>Photo title<input name="title" required></label><label>Image URL<input type="url" name="uri" required placeholder="https://…"></label><label>Who or what is pictured?<input name="description"></label><button>Add familiar photo</button></form></section>
<section><h2>Talk with FRED</h2><button type="button" id="talkButton">Hold to talk</button><p id="voiceStatus" role="status" aria-live="assertive">Press and hold while speaking.</p><div class="chat" id="chat" aria-live="polite">{chat}</div><form method="post" action="/conversation"><label>Or type a message<input name="message" required autocomplete="off" placeholder="Tell me about your day"></label><button>Send</button></form><form method="post" action="/conversation/clear"><button>Clear private conversation</button></form><p class="warning">Audio is recorded only while the button is held. This robot is not a person, clinician, or emergency service.</p></section>
</main><dialog id="viewer"><button onclick="viewer.close()">Close</button><h2 id="mediaTitle"></h2><img id="mediaImage"><p id="mediaDescription"></p></dialog><script>
function showMedia(card){{const{{uri,title,description}}=card.dataset;mediaTitle.textContent=title;mediaImage.src=uri;mediaImage.alt=description||title;mediaDescription.textContent=description;viewer.showModal()}}
chat.scrollTop=chat.scrollHeight;const talk=document.getElementById('talkButton'),status=document.getElementById('voiceStatus');let recorder,chunks=[],stream;
async function setRobotStatus(state){{try{{await fetch('/api/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{state}})}})}}catch(e){{}}}}
async function startTalking(event){{event.preventDefault();if(recorder?.state==='recording')return;try{{stream=await navigator.mediaDevices.getUserMedia({{audio:true}});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>{{if(e.data.size)chunks.push(e.data)}};recorder.onstop=sendAudio;recorder.start();setRobotStatus('listening');talk.classList.add('recording');talk.textContent='Listening… release to send';status.textContent='Listening. Release the button when finished.'}}catch(e){{status.textContent='Microphone unavailable. Check browser permission and HTTPS.'}}}}
function stopTalking(event){{event.preventDefault();if(recorder?.state==='recording')recorder.stop()}}
async function sendAudio(){{talk.classList.remove('recording');talk.disabled=true;talk.textContent='Thinking…';status.textContent='Turning speech into text…';stream?.getTracks().forEach(t=>t.stop());try{{const blob=new Blob(chunks,{{type:recorder.mimeType||'audio/webm'}});const bytes=new Uint8Array(await blob.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));const response=await fetch('/api/voice',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{audio:btoa(binary),content_type:blob.type}})}});const data=await response.json();if(!response.ok)throw new Error(data.error||'Voice request failed');appendTurn('user','You',data.transcript);appendTurn('assistant','Companion',data.reply);status.textContent='FRED said: '+data.reply;speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(data.reply);utterance.rate=.9;utterance.onend=()=>setRobotStatus('idle');speechSynthesis.speak(utterance)}}catch(e){{status.textContent=e.message;setRobotStatus('alert')}}finally{{talk.disabled=false;talk.textContent='Hold to talk'}}}}
function appendTurn(role,label,text){{const div=document.createElement('div');div.className='turn '+role;const b=document.createElement('b');b.textContent=label;div.append(b,document.createTextNode(text));chat.append(div);chat.scrollTop=chat.scrollHeight}}
for(const event of ['pointerdown'])talk.addEventListener(event,startTalking);for(const event of ['pointerup','pointercancel','pointerleave'])talk.addEventListener(event,stopTalking);
</script></body></html>"""
    return document.encode()


def make_handler(app: RobotApplication):
    class Handler(BaseHTTPRequestHandler):
        def _redirect(self, notice: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/?notice=" + notice.replace(" ", "+"))
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
                except (KeyError, ValueError, json.JSONDecodeError) as error:
                    self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST); return
                except Exception:
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
                if self.path == "/conversation/clear":
                    app.store.clear_conversation(); self._redirect("Conversation cleared"); return
            except (KeyError, ValueError) as error:
                self.send_error(HTTPStatus.BAD_REQUEST, str(error)); return
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
