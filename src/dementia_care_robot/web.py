import html
import mimetypes
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
from .models import FamiliarMedia, Reminder
from .scheduler import ReminderScheduler
from .storage import SQLiteStore


class RobotApplication:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir = data_dir / "media"
        self.media_dir.mkdir(exist_ok=True)
        self.store = SQLiteStore(data_dir / "robot.db")
        notifier, speaker = ConsoleCaregiverNotifier(), ConsoleSpeaker()
        self.scheduler = ReminderScheduler(self.store, CareCoordinator(speaker, notifier))
        model = OpenAICompatibleModel.from_environment() or OfflineCompanion()
        self.conversation = ConversationService(self.store, model, notifier)


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
:root{{--ink:#20302d;--paper:#f7f3e8;--card:#fffdf8;--teal:#276b63;--gold:#e4ad4d}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:18px/1.5 system-ui,sans-serif}}header{{background:var(--teal);color:white;padding:20px 5vw;display:flex;justify-content:space-between;align-items:center}}header h1{{margin:0;font-size:clamp(1.5rem,4vw,2.3rem)}}header span{{font-size:.9rem}}main{{max-width:1200px;margin:auto;padding:28px 5vw;display:grid;gap:24px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}section{{background:var(--card);padding:24px;border-radius:18px;box-shadow:0 4px 18px #243b3520}}h2{{margin-top:0}}label{{display:block;font-weight:650;margin-top:12px}}input,button{{font:inherit}}input{{width:100%;padding:12px;border:2px solid #9aa9a5;border-radius:9px}}button{{cursor:pointer;border:0;border-radius:10px;padding:12px 18px;background:var(--teal);color:white;font-weight:700;margin-top:14px}}button:focus,input:focus{{outline:4px solid var(--gold);outline-offset:2px}}ul{{padding:0;list-style:none}}li{{border-bottom:1px solid #ddd;padding:11px 0}}time{{display:block;color:#52645f}}.gallery{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.media-card{{margin:0;padding:0;overflow:hidden;background:#eee;color:var(--ink)}}.media-card img{{width:100%;height:140px;object-fit:cover;display:block}}.media-card span{{display:block;padding:9px}}.chat{{max-height:330px;overflow:auto}}.turn{{padding:12px;margin:8px 0;border-radius:12px;background:#e6efed}}.turn.user{{background:#f6e7c8}}.turn b{{display:block;font-size:.8rem}}.notice{{grid-column:1/-1;background:#fff2c8;padding:12px;border-radius:10px}}dialog{{max-width:800px;border:0;border-radius:18px;padding:20px}}dialog img{{max-width:100%;max-height:65vh}}.warning{{font-size:.85rem;color:#5e5140}}@media(max-width:500px){{main{{padding:15px}}section{{padding:18px}}}}
</style></head><body><header><h1>Care Companion</h1><span>I am a robot assistant</span></header><main>
{f'<div class="notice" role="status">{html.escape(notice)}</div>' if notice else ''}
<section><h2>Today’s reminders</h2><ul>{reminder_cards}</ul><form method="post" action="/reminders"><label>Reminder<input name="message" maxlength="200" required placeholder="Time for a glass of water"></label><label>Date and time<input type="datetime-local" name="due_at" required></label><button>Schedule reminder</button></form></section>
<section><h2>Familiar photos</h2><div class="gallery">{media_cards}</div><form method="post" action="/media"><label>Photo title<input name="title" required></label><label>Image URL<input type="url" name="uri" required placeholder="https://…"></label><label>Who or what is pictured?<input name="description"></label><button>Add familiar photo</button></form></section>
<section><h2>Conversation</h2><div class="chat" id="chat" aria-live="polite">{chat}</div><form method="post" action="/conversation"><label>Say something<input name="message" required autocomplete="off" placeholder="Tell me about your day"></label><button>Send</button></form><form method="post" action="/conversation/clear"><button>Clear private conversation</button></form><p class="warning">This prototype can listen and offer companionship, but it is not a person, clinician, or emergency service.</p></section>
</main><dialog id="viewer"><button onclick="viewer.close()">Close</button><h2 id="mediaTitle"></h2><img id="mediaImage"><p id="mediaDescription"></p></dialog><script>function showMedia(card){{const{{uri,title,description}}=card.dataset;mediaTitle.textContent=title;mediaImage.src=uri;mediaImage.alt=description||title;mediaDescription.textContent=description;viewer.showModal()}}chat.scrollTop=chat.scrollHeight</script></body></html>"""
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
            length = min(int(self.headers.get("Content-Length", "0")), 16_384)
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

        def log_message(self, format: str, *args: object) -> None:
            print("WEB:", format % args)
    return Handler


def serve(data_dir: str = "data", host: str = "127.0.0.1", port: int = 8080, open_browser: bool = False) -> None:
    app = RobotApplication(Path(data_dir))
    server = ThreadingHTTPServer((host, port), make_handler(app))
    stop = threading.Event()
    def scheduler_loop() -> None:
        while not stop.wait(1):
            app.scheduler.deliver_due()
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"Care Companion running at http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
