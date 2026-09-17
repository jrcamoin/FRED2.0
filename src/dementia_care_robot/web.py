"""Dependency-free resident and caregiver web interfaces for the local device."""

import base64, html, json, mimetypes, os, shutil, socket, ssl, subprocess, threading, uuid, webbrowser
from datetime import UTC, datetime
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .api_errors import RemoteServiceError
from .adapters import ConsoleSpeaker
from .conversation import ConversationService, OfflineCompanion, OpenAICompatibleModel
from .coordinator import CareCoordinator
from .hardware import PicoBridge
from .models import Assessment, CareProfile, CaregiverContact, FamiliarMedia, Reminder, ReminderStatus, ResponseFeedback, RiskLevel
from .notifications import DeliveryNotifier
from .scheduler import ReminderScheduler
from .security import DeviceSecrets
from .speech import OpenAITranscriber, SpeechNotConfigured
from .storage import SQLiteStore
from .website import landing_page, fred_page, public_asset

CSS="""*{box-sizing:border-box}body{margin:0;background:#f1f5f7;color:#193247;font:17px/1.5 system-ui,sans-serif}header{background:#16344d;color:white;padding:18px 5vw;display:flex;justify-content:space-between;align-items:center}header a{color:white}main{max-width:1100px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:2fr 1fr;gap:20px}.card{background:white;border:1px solid #d8e2e7;border-radius:18px;padding:22px;margin-bottom:20px;box-shadow:0 4px 18px #16344d0d}h1,h2,h3{margin-top:0}button,.button{border:0;border-radius:12px;background:#14766e;color:white;font-weight:750;padding:13px 18px;min-height:48px;cursor:pointer;text-decoration:none;display:inline-block}button.danger{background:#a3342c}input,select,textarea{width:100%;padding:11px;border:1px solid #aebec8;border-radius:9px;font:inherit;margin:5px 0 12px}label{font-weight:700}.muted{color:#607484;font-size:.88rem}.notice{background:#fff3ca;border-left:5px solid #dfaa2b;padding:12px;margin-bottom:18px}.status{display:inline-block;border-radius:99px;background:#e6f4f1;padding:4px 10px}.reminder{border-top:1px solid #dce5e9;padding:14px 0}.gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.gallery img{width:100%;height:150px;object-fit:cover;border-radius:10px}.chat{height:300px;overflow:auto;background:#f7fafb;padding:12px;border-radius:12px}.turn{margin:8px;padding:10px;background:#e7f1f6;border-radius:10px}.turn.user{background:#173a56;color:white;margin-left:20%}.talk{font-size:1.15rem;width:100%;background:#bd443b}.actions{display:flex;gap:10px;flex-wrap:wrap}.metric{font-size:2rem;font-weight:800}.steps{display:flex;gap:8px;margin-bottom:18px}.steps span{background:#e4ecef;padding:6px 11px;border-radius:99px}.steps .active{background:#14766e;color:white}@media(max-width:760px){.grid{grid-template-columns:1fr}.gallery{grid-template-columns:repeat(2,1fr)}header{align-items:flex-start;gap:10px}.actions{flex-direction:column}}"""

# Temporary prototype setting. Change to True to restore the preserved
# caregiver onboarding, login, session cookie, and POST-route protection.
CAREGIVER_AUTH_ENABLED = False

def _layout(title, body, caregiver=False):
    links = '<a href="/">Human Frame Robotics ↗</a><a href="/fred">Meet FRED</a>'
    links += f'<a href="/app" {"aria-current=page" if not caregiver else ""}>Companion</a>'
    links += f'<a href="/caregiver" {"aria-current=page" if caregiver else ""}>Caregiver</a>'
    mode = "Caregiver workspace" if caregiver else "Your companion space"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#263f36"><title>{html.escape(title)} · Human Frame Robotics</title><style>{CSS}</style><link rel="stylesheet" href="/static/site/app.css"></head><body class="{'caregiver' if caregiver else 'resident'}"><a class="skip-link" href="#main">Skip to content</a><header><a class="app-brand" href="/app"><span class="fred-icon" aria-hidden="true">••</span><span>FRED<small>by Human Frame Robotics</small></span></a><nav class="actions" aria-label="App navigation">{links}</nav></header><main id="main"><div class="workspace-label"><span>{mode}</span><span>Local prototype</span></div>{body}</main><footer class="app-footer"><span>Human Frame Robotics · Thoughtfully connected.</span><a href="/fred">About FRED</a></footer></body></html>'''.encode()

class RobotApplication:
    def __init__(self,data_dir:Path,pico_device=None):
        data_dir.mkdir(parents=True,exist_ok=True); self.data_dir=data_dir; self.media_dir=data_dir/"media"; self.media_dir.mkdir(exist_ok=True)
        self.secrets=DeviceSecrets(data_dir); self.store=SQLiteStore(data_dir/"robot.db",self.secrets)
        self.notifier=DeliveryNotifier(self.store); self.scheduler=ReminderScheduler(self.store,CareCoordinator(ConsoleSpeaker(),self.notifier))
        model=OpenAICompatibleModel.from_environment() or OfflineCompanion(); self.generated_responses=isinstance(model,OpenAICompatibleModel); self.response_mode="online" if self.generated_responses else "offline"
        self.conversation=ConversationService(self.store,model,self.notifier); self.transcriber=OpenAITranscriber.from_environment(); self.server_transcription=self.transcriber is not None
        self.started_at=datetime.now(UTC); self.pico=PicoBridge(pico_device,self._hardware_event) if pico_device else None
        if self.pico:self.pico.start()
        self.store.record_health("boot","ok")
    def _hardware_event(self,switch,action):
        if switch=="help" and action=="press": self.notifier.notify(Assessment(RiskLevel.URGENT,"The physical help switch was pressed.","I am alerting your configured support person.")); self.set_status("alert")
        if switch=="action" and action=="press":
            delivered=[r for r in self.store.list_reminders(True) if r.status==ReminderStatus.DELIVERED]
            if delivered:self.store.acknowledge_reminder(delivered[-1].reminder_id,ReminderStatus.ACKNOWLEDGED,datetime.now(UTC)); self.set_status("idle")
    def set_status(self,state):
        if self.pico:self.pico.set_led(state)
    def voice_turn(self,audio,content_type):
        if not self.transcriber:raise SpeechNotConfigured("Voice transcription is unavailable. Please type while testing.")
        self.set_status("thinking")
        try:
            transcript=self.transcriber.transcribe(audio,content_type); reply,risk=self.conversation.respond(transcript); self.set_status("alert" if risk is RiskLevel.URGENT else "speaking"); return transcript,reply,risk.value
        except Exception:self.set_status("idle");raise
    def health(self):
        disk=shutil.disk_usage(self.data_dir); network=False
        try:
            with socket.create_connection(("1.1.1.1",53),timeout=.4):network=True
        except OSError:pass
        power="connected"
        supplies=Path("/sys/class/power_supply")
        if supplies.exists():
            online=list(supplies.glob("*/online"))
            if online:
                try:power="connected" if any(p.read_text().strip()=="1" for p in online) else "battery"
                except OSError:power="unknown"
        if shutil.which("vcgencmd"):
            try:
                throttled=subprocess.run(["vcgencmd","get_throttled"],capture_output=True,text=True,timeout=2).stdout.strip()
                if throttled not in {"throttled=0x0",""}: power="undervoltage/throttling detected"
            except (OSError,subprocess.SubprocessError): pass
        self.store.record_health("heartbeat","ok")
        pico_status=(f"connected ({self.pico.resolved_device})" if self.pico and self.pico.connected else f"reconnecting ({self.pico.last_error or 'searching'})" if self.pico else "not configured")
        return {"power":power,"network":"online" if network else "offline","pico":pico_status,"disk_free_gb":round(disk.free/1024**3,1),"uptime":str(datetime.now(UTC)-self.started_at).split('.')[0],"last_check_in":self.store.last_health("check_in")}

def _page(app,notice=""):
    """Render the resident-facing conversation, reminder, and photo screen."""
    media=app.store.list_media(); turns=app.store.conversation(); all_r=app.store.list_reminders(True); delivered=[r for r in all_r if r.status==ReminderStatus.DELIVERED]
    current=delivered[-1] if delivered else None
    reminder=(f'<div class="card"><h2>{html.escape(current.message)}</h2>{f"<audio controls autoplay src=\"{html.escape(current.voice_note_uri)}\"></audio>" if current.voice_note_uri else ""}<div class="actions"><form method="post" action="/reminder/{current.reminder_id}/ack"><button>I’ve done this</button></form><form method="post" action="/reminder/{current.reminder_id}/help"><button class="danger">I need help</button></form></div></div>' if current else '')
    gallery=''.join(f'<figure><img src="{html.escape(m.uri)}" alt="{html.escape(m.description or m.title)}"><figcaption>{html.escape(m.title)}</figcaption></figure>' for m in media if m.kind=="image") or '<div class="empty-state"><span aria-hidden="true">♡</span><h3>A place for familiar faces</h3><p>Your caregiver can add photos of the people and moments you love.</p></div>'
    chat=''.join(f'<div class="turn {t.role}"><b>{"You" if t.role=="user" else "FRED"}</b><br>{html.escape(t.content)}</div>' for t in turns) or '<div class="chat-empty"><p>It’s good to spend time with you.</p><span>Tell me about your day, or ask me something.</span></div>'
    body=f'{f"<div class=notice>{html.escape(notice)}</div>" if notice else ""}{reminder}<div class="grid"><section class="card"><div class="companion-heading"><span class="fred-icon" aria-hidden="true">••</span><div><p class="eyebrow">A moment together</p><h1>Hello. I’m FRED,<br>your robot helper.</h1></div></div><button class="talk" id="talkButton" data-server-transcription="{str(app.server_transcription).lower()}">Start speaking</button><p id="voiceStatus" class="muted" role="status">{"Press Start speaking, or type a message below." if not app.server_transcription else "You can also type below."}</p><div class="chat" id="chat" role="log" aria-label="Conversation with FRED" aria-live="polite">{chat}</div><form id="messageForm"><label class="sr-only" for="messageInput">Your message to FRED</label><input id="messageInput" required maxlength="2000" placeholder="Ask FRED something"><button>Send message →</button></form><form class="clear-form" method="post" action="/conversation/clear" onsubmit="return confirm(\'Clear this conversation from FRED?\')"><button class="danger">Clear conversation</button></form></section><aside><section class="card"><h2>Familiar photos</h2><div class="gallery">{gallery}</div></section><section class="card"><h2>Need a person?</h2><p>Press the physical HELP button on FRED.</p></section></aside></div><script>{_resident_js()}</script>'
    return _layout("FRED",body)

def _resident_js():
    return """const q=x=>document.getElementById(x),chat=q('chat'),form=q('messageForm'),input=q('messageInput'),status=q('voiceStatus'),talk=q('talkButton');function add(role,text){chat.querySelector('.chat-empty')?.remove();let d=document.createElement('div');d.className='turn '+role;d.textContent=text;chat.append(d);chat.scrollTop=chat.scrollHeight}function hardware(state){fetch('/api/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({state})}).catch(()=>{})}function speak(text){if('speechSynthesis'in window){let u=new SpeechSynthesisUtterance(text);u.onend=()=>hardware('idle');u.onerror=()=>hardware('idle');window.speechSynthesis.speak(u)}else hardware('idle')}let sending=false;async function send(message){if(sending)return;sending=true;form.querySelector('button').disabled=true;add('user',message);status.textContent='Thinking…';try{let r=await fetch('/api/conversation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})}),d=await r.json();if(!r.ok)throw new Error(d.error||'The request failed.');add('assistant',d.reply);status.textContent='Ready';speak(d.reply)}catch(e){status.textContent=e.message;input.value=message;hardware('idle')}finally{sending=false;form.querySelector('button').disabled=false;input.focus()}}form.onsubmit=e=>{e.preventDefault();let t=input.value.trim();if(t&&!sending){input.value='';send(t)}};const server=talk.dataset.serverTranscription==='true',SR=window.SpeechRecognition||window.webkitSpeechRecognition;let recorder,chunks=[],stream;async function uploadRecording(blob){status.textContent='Thinking…';let bytes=new Uint8Array(await blob.arrayBuffer()),binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));try{let r=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audio:btoa(binary),content_type:blob.type||'audio/webm'})}),d=await r.json();if(!r.ok)throw new Error(d.error||'The recording could not be processed.');add('user',d.transcript);add('assistant',d.reply);status.textContent='Ready';speak(d.reply)}catch(e){status.textContent=e.message;hardware('idle')}finally{talk.disabled=false}}if(server&&navigator.mediaDevices&&window.MediaRecorder){talk.disabled=false;talk.onclick=async()=>{if(recorder&&recorder.state==='recording'){recorder.stop();talk.textContent='Start speaking';return}try{stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());talk.disabled=true;uploadRecording(new Blob(chunks,{type:recorder.mimeType||'audio/webm'}))};recorder.start();hardware('listening');talk.textContent='Stop speaking';status.textContent='Listening…'}catch(e){status.textContent='Microphone access failed. Please type below.'}}}else if(SR){talk.disabled=false;talk.onclick=()=>{let r=new SR();r.lang=navigator.language;r.onresult=e=>{hardware('idle');input.value=e.results[0][0].transcript;status.textContent='Check what I heard, then press Send.'};r.onerror=()=>{hardware('idle');status.textContent='I could not hear that. Please type below.'};r.start();hardware('listening');status.textContent='Listening…'}}else{talk.disabled=true;status.textContent='Voice is unavailable in this browser. Please type below.'}"""

def _login(notice=""):
    return _layout("Caregiver sign in",f'<section class="card" style="max-width:480px;margin:auto"><h1>Caregiver sign in</h1>{f"<div class=notice>{html.escape(notice)}</div>" if notice else ""}<form method="post" action="/login"><label>Password<input type="password" name="password" required></label><button>Sign in</button></form></section>',True)

def _onboarding(step=1,notice=""):
    bodies={1:'<h1>Set up FRED</h1><p>This guided setup usually takes under 15 minutes.</p><form method="post" action="/onboarding"><input type="hidden" name="step" value="1"><label>Caregiver password<input type="password" minlength="10" name="password" required></label><label>Confirm password<input type="password" minlength="10" name="confirm" required></label><button>Continue</button></form>',2:'<h1>Quiet hours</h1><form method="post" action="/onboarding"><input type="hidden" name="step" value="2"><label>Quiet starts<input type="time" name="quiet_start" value="21:00"></label><label>Quiet ends<input type="time" name="quiet_end" value="07:00"></label><button>Continue</button></form>',3:'<h1>Caregiver contact</h1><form method="post" action="/onboarding"><input type="hidden" name="step" value="3"><label>Name<input name="name" required></label><label>Alert channel<select name="channel"><option value="sms">SMS via Twilio</option><option value="push">Push webhook</option></select></label><label>Phone number or webhook URL<input name="destination" required></label><button>Finish setup</button></form>'}
    return _layout("Set up FRED",f'<div class="steps"><span class="{"active" if step==1 else ""}">1 Security</span><span class="{"active" if step==2 else ""}">2 Schedule</span><span class="{"active" if step==3 else ""}">3 Contact</span></div>{f"<div class=notice>{html.escape(notice)}</div>" if notice else ""}<section class=card>{bodies[step]}</section>',True)

def _caregiver(app,notice=""):
    """Render caregiver controls for reminders, media, alerts, and feedback."""
    summary=app.store.daily_summary(); health=app.health(); reminders=app.store.list_reminders(True); deliveries=app.store.deliveries(); contacts=app.store.contacts()
    rs=''.join(f'<div class=reminder><b>{html.escape(r.message)}</b><br><span class=status>{r.status.value}</span> · {r.due_at.astimezone().strftime("%b %d, %I:%M %p")} · {r.recurrence}</div>' for r in reminders) or '<p>No reminders yet.</p>'
    ds=''.join(f'<div class=reminder><b>{d.risk.value.upper()}</b> {html.escape(d.reason)}<br>{d.status}, {d.attempts} attempt(s)</div>' for d in deliveries) or '<p>No alerts today.</p>'
    cs=', '.join(html.escape(c.name)+" ("+html.escape(c.channel)+")" for c in contacts) or 'None configured'
    feedback=''.join(f'''<div class="reminder"><b>Resident:</b> {html.escape(pair["prompt"])}<br><b>FRED:</b> {html.escape(pair["response"])}{f'<p class="status">Reviewed: {html.escape(pair["rating"])}</p>' if pair["rating"] else f'''<form method="post" action="/feedback"><input type="hidden" name="turn_id" value="{pair["assistant_turn_id"]}"><label>Rating<select name="rating"><option value="helpful">Helpful</option><option value="confusing">Confusing</option><option value="unsafe">Unsafe</option></select></label><label>Better response (optional)<textarea name="correction" maxlength="2000"></textarea></label><label>Approved fact to remember (optional)<input name="memory" maxlength="500" placeholder="Example: Jo's glasses are beside the blue chair"></label><p class="muted">Only enter a memory the caregiver has verified.</p><button>Save review</button></form>'''}</div>''' for pair in app.store.conversation_pairs()) or '<p>No conversation responses to review yet.</p>'
    memories=''.join(f'<div class="reminder">{html.escape(memory.content)}<form method="post" action="/memory/{memory.memory_id}/delete"><button class="danger">Forget this</button></form></div>' for memory in app.store.approved_memories()) or '<p class="muted">No approved memories yet.</p>'
    last=health['last_check_in'].astimezone().strftime('%b %d, %I:%M %p') if health['last_check_in'] else 'No check-in yet'
    body=f'{f"<div class=notice>{html.escape(notice)}</div>" if notice else ""}<div class="dashboard-heading"><div><p class="eyebrow">Care, with a personal touch</p><h1>Today at a glance</h1><p class="muted">Small details that help FRED feel more familiar.</p></div><a class="button" href="/app">Open companion ↗</a></div><nav class="dashboard-nav" aria-label="Caregiver sections"><a href="#reminders">Reminders</a><a href="#family-media">Family media</a><a href="#reviews">Response reviews</a><a href="#settings">Contacts & settings</a></nav><div class=grid><div><section class=card><div class=actions><div><div class=metric>{summary.get("acknowledged",0)}</div>Acknowledged</div><div><div class=metric>{summary.get("needs_help",0)}</div>Needed help</div><div><div class=metric>{summary.get("alerts",0)}</div>Alerts</div></div></section><section class=card id="reminders"><h2>Reminders</h2>{rs}<h3>Add reminder</h3><form method=post action=/reminders><label>Message<input name=message maxlength=200 required></label><label>Date and time<input type=datetime-local name=due_at required></label><label>Repeat<select name=recurrence><option value=none>Once</option><option value=daily>Daily</option><option value=weekly>Weekly</option></select></label><label>Family voice note (optional)<select name=voice_note_uri><option value="">None</option>{"".join(f"<option value=\"{html.escape(m.uri)}\">{html.escape(m.title)}</option>" for m in app.store.list_media() if m.kind=="audio")}</select></label><button>Schedule</button></form></section><section class=card id="reviews"><h2>Review FRED responses</h2><p class=muted>Ratings build a test set. Only caregiver-approved memories are used in later conversations.</p>{feedback}</section><section class=card><h2>Recent alert delivery</h2>{ds}</section></div><aside><section class=card><h2>Device health</h2><p>Power: <b>{health["power"]}</b><br>Network: <b>{health["network"]}</b><br>Pico: <b>{health["pico"]}</b><br>Free storage: <b>{health["disk_free_gb"]} GB</b><br>Uptime: <b>{health["uptime"]}</b><br>Last check-in: <b>{last}</b></p></section><section class=card><h2>Approved memories</h2>{memories}</section><section class=card id="family-media"><h2>Upload family media</h2><form method=post enctype=multipart/form-data action=/upload><label>Title<input name=title required maxlength=120></label><label>Description<input name=description maxlength=300></label><label>Photo or voice note<input type=file name=file accept="image/jpeg,image/png,image/webp,audio/webm,audio/mpeg,audio/wav" required></label><button>Encrypt and upload</button></form></section><section class=card id="settings"><h2>Settings</h2><p>Contacts: {cs}</p><form method=post action=/contacts><label>Name<input name=name required></label><label>Channel<select name=channel><option value=sms>SMS</option><option value=push>Push webhook</option></select></label><label>Destination<input name=destination required></label><button>Add contact</button></form><hr><form method=post action=/data/delete onsubmit="return confirm(\'Delete all personal data? This cannot be undone.\')"><button class=danger>Delete personal data</button></form></section></aside></div>'
    recorder='''<script>
const record=document.getElementById('recordVoice'), recordingStatus=document.getElementById('recordingStatus');
let mediaRecorder, chunks=[], recordingStream;
record.onclick=async()=>{
    if(mediaRecorder?.state==='recording'){record.disabled=true;record.textContent='Saving…';mediaRecorder.stop();return;}
    const title=document.getElementById('voiceTitle');
    if(!title.value.trim()){recordingStatus.textContent='Add a title before recording.';title.focus();return;}
    if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){recordingStatus.textContent='Recording is unavailable in this browser. You can upload an existing voice note below.';return;}
    record.disabled=true;
    try{
        recordingStream=await navigator.mediaDevices.getUserMedia({audio:true});
        chunks=[];mediaRecorder=new MediaRecorder(recordingStream);
        mediaRecorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
        mediaRecorder.onstop=async()=>{
            recordingStream.getTracks().forEach(track=>track.stop());
            try{
                const blob=new Blob(chunks,{type:mediaRecorder.mimeType||'audio/webm'}),data=new FormData();
                data.append('title',title.value.trim());data.append('description','Family-recorded reminder');data.append('file',blob,'voice-note.webm');
                const response=await fetch('/upload',{method:'POST',body:data});
                if(!response.ok)throw new Error('The voice note could not be saved. Please try again or upload a file.');
                location.href=response.url;
            }catch(error){recordingStatus.textContent=error.message;record.disabled=false;record.textContent='Record a family voice note';}
        };
        mediaRecorder.start();record.textContent='Stop and save';recordingStatus.textContent='Recording. Press Stop and save when you’re finished.';
    }catch(error){recordingStream?.getTracks().forEach(track=>track.stop());recordingStatus.textContent='Microphone access is unavailable. Check your browser permission or upload a voice note below.';}
    finally{record.disabled=false;}
};
</script>'''
    body=body.replace('<h2>Upload family media</h2>','<h2>Upload family media</h2><label>Voice-note title<input id="voiceTitle" maxlength="120"></label><button type="button" id="recordVoice">Record a family voice note</button><p id="recordingStatus" role="status" class="muted">Or upload an existing photo or voice note below.</p>')+recorder
    return _layout("Caregiver dashboard",body,True)

def _multipart(handler,length):
    """Parse the limited multipart form format used for local media uploads."""
    raw=b"Content-Type: "+handler.headers["Content-Type"].encode()+b"\r\nMIME-Version: 1.0\r\n\r\n"+handler.rfile.read(length); msg=BytesParser(policy=default).parsebytes(raw); result={}
    for part in msg.iter_parts():
        name=part.get_param("name",header="content-disposition"); filename=part.get_filename(); data=part.get_payload(decode=True)
        result[name]=(filename,part.get_content_type(),data) if filename else data.decode(errors="replace")
    return result

# Bind an application instance to a standard-library HTTP handler class. The
# unusual one-space indentation below keeps the existing compact handler intact.
def make_handler(app):
 class Handler(BaseHTTPRequestHandler):
    def auth(self):
        c=SimpleCookie(self.headers.get("Cookie","")); return "fred_session" in c and app.secrets.valid_session(c["fred_session"].value)
    def redirect(self,path,notice=""):
        self.send_response(303); self.send_header("Location",path+("?notice="+quote(notice) if notice else "")); self.end_headers()
    def send(self,body,status=200,kind="text/html; charset=utf-8"):
        self.send_response(status); self.send_header("Content-Type",kind); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def json(self,payload,status=200):self.send(json.dumps(payload).encode(),status,"application/json")
    def form(self,limit=20000):
        length=int(self.headers.get("Content-Length","0"));
        if length>limit:raise ValueError("Request too large")
        return {k:v[0] for k,v in parse_qs(self.rfile.read(length).decode()).items()}
    def do_GET(self):
        # GET routes render the two interfaces and decrypt uploaded media only
        # when it is requested; encrypted bytes remain on disk at rest.
        p=urlparse(self.path); notice=parse_qs(p.query).get("notice",[""])[0]
        if p.path=="/":self.send(landing_page());return
        if p.path in {"/fred", "/fred/"}:self.send(fred_page());return
        if p.path.startswith("/static/site/"):
            asset=public_asset(p.path)
            if asset is not None:self.send(asset,kind=mimetypes.guess_type(p.path)[0] or "application/octet-stream");return
            self.send_error(404);return
        if p.path in {"/app", "/app/"}:app.scheduler.deliver_due();self.send(_page(app,notice));return
        if p.path=="/caregiver":
            if CAREGIVER_AUTH_ENABLED and not app.store.configured():self.send(_onboarding());return
            self.send(_caregiver(app,notice) if not CAREGIVER_AUTH_ENABLED or self.auth() else _login(notice));return
        if p.path.startswith("/local-media/"):
            path=app.media_dir/(Path(p.path).name+".enc")
            if path.is_file():
                try:self.send(app.secrets.decrypt_bytes(path.read_bytes()),kind=mimetypes.guess_type(Path(p.path).name)[0] or "application/octet-stream")
                except Exception:self.send_error(500)
                return
        self.send_error(404)
    def do_POST(self):
        # Public resident actions are handled before the caregiver auth gate.
        # Caregiver mutations below the gate are temporarily open while
        # CAREGIVER_AUTH_ENABLED is False during local prototyping.
        p=urlparse(self.path).path; length=int(self.headers.get("Content-Length","0"))
        if p=="/api/delivery-status":
            supplied=parse_qs(urlparse(self.path).query).get("token",[""])[0]
            if not supplied or supplied!=os.environ.get("ROBOT_DELIVERY_CALLBACK_TOKEN",""):self.send_error(403);return
            try:
                f=self.form(4096); updated=app.store.update_delivery_status(f["MessageSid"],f["MessageStatus"]);self.send(b"ok" if updated else b"unknown",200,"text/plain");return
            except (KeyError,ValueError):self.send_error(400);return
        if p=="/api/conversation":
            try:
                if not 0<length<=16384:raise ValueError("Message is too large or empty.")
                data=json.loads(self.rfile.read(length)); message=data.get("message") if isinstance(data,dict) else None
                if not isinstance(message,str) or not message.strip() or len(message)>2000:raise ValueError("Enter a valid message of 1–2000 characters.")
                app.set_status("thinking"); reply,risk=app.conversation.respond(message.strip()); app.set_status("alert" if risk is RiskLevel.URGENT else "speaking"); app.store.record_health("check_in","conversation"); self.json({"reply":reply,"risk":risk.value});return
            except (ValueError,json.JSONDecodeError) as e:app.set_status("idle");self.json({"error":str(e)},400);return
            except RemoteServiceError as e:app.set_status("idle");self.json({"error":str(e)},502);return
        if p=="/api/status":
            try:
                if not 0<length<=128:raise ValueError("Invalid hardware status")
                state=json.loads(self.rfile.read(length)).get("state")
                if state not in {"idle","listening"}:raise ValueError("Invalid hardware status")
                app.set_status(state);self.json({"status":state});return
            except (AttributeError,ValueError,json.JSONDecodeError) as e:self.json({"error":str(e)},400);return
        if p=="/api/voice":
            try:
                if length>12_000_000:raise ValueError("Recording is too large")
                data=json.loads(self.rfile.read(length)); audio=base64.b64decode(data["audio"],validate=True); transcript,reply,risk=app.voice_turn(audio,str(data.get("content_type","audio/webm"))); app.store.record_health("check_in","voice");self.json({"transcript":transcript,"reply":reply,"risk":risk});return
            except SpeechNotConfigured as e:self.json({"error":str(e)},503);return
            except Exception as e:self.json({"error":str(e)},400);return
        if p=="/conversation/clear":
            app.store.clear_conversation();app.set_status("idle");self.redirect("/app","Conversation cleared.");return
        if p.startswith("/reminder/"):
            parts=p.split("/"); status=ReminderStatus.ACKNOWLEDGED if parts[-1]=="ack" else ReminderStatus.NEEDS_HELP; ok=app.store.acknowledge_reminder(parts[-2],status,datetime.now(UTC))
            if status==ReminderStatus.NEEDS_HELP:app.notifier.notify(Assessment(RiskLevel.CAREGIVER,"Help requested for a reminder.","I have recorded that you need help."))
            app.store.record_health("check_in",status.value);app.set_status("idle");self.redirect("/app","Thank you. Your response was recorded." if ok else "Reminder not found.");return
        if p=="/onboarding":
            try:
                f=self.form();step=int(f["step"])
                if step==1:
                    if len(f.get("password",""))<10 or f["password"]!=f.get("confirm"):raise ValueError("Passwords must match and contain at least 10 characters.")
                    app.store.set_setting("caregiver_password_hash",DeviceSecrets.hash_password(f["password"]));self.send(_onboarding(2));return
                if step==2:app.store.set_setting("quiet_start",f["quiet_start"]);app.store.set_setting("quiet_end",f["quiet_end"]);self.send(_onboarding(3));return
                if step==3:app.store.add_contact(CaregiverContact(uuid.uuid4().hex,f["name"],f["channel"],f["destination"]));self.redirect("/caregiver","Setup complete. Sign in.");return
            except (KeyError,ValueError) as e:self.send(_onboarding(max(1,min(3,int(locals().get('step',1)))),str(e)),400);return
        if p=="/login":
            f=self.form(); stored=app.store.setting("caregiver_password_hash")
            if not DeviceSecrets.verify_password(f.get("password",""),stored):self.send(_login("Incorrect password."),401);return
            self.send_response(303);self.send_header("Location","/caregiver");self.send_header("Set-Cookie",f"fred_session={app.secrets.issue_session()}; HttpOnly; SameSite=Strict; Path=/");self.end_headers();return
        if CAREGIVER_AUTH_ENABLED and not self.auth():self.send(_login("Please sign in."),401);return
        try:
            if p=="/reminders":
                f=self.form(); local=datetime.fromisoformat(f["due_at"]).astimezone(); rec=f.get("recurrence","none")
                if rec not in {"none","daily","weekly"}:raise ValueError("Invalid recurrence")
                app.scheduler.schedule(Reminder(uuid.uuid4().hex,f["message"].strip(),local,rec,voice_note_uri=f.get("voice_note_uri","")));self.redirect("/caregiver","Reminder scheduled.");return
            if p=="/contacts":
                f=self.form(); channel=f["channel"]; destination=f["destination"].strip()
                if channel=="sms" and not destination.startswith("+"):raise ValueError("Use an international phone number beginning with +.")
                if channel=="push" and urlparse(destination).scheme!="https":raise ValueError("Push webhook must use HTTPS.")
                app.store.add_contact(CaregiverContact(uuid.uuid4().hex,f["name"].strip(),channel,destination));self.redirect("/caregiver","Caregiver contact added.");return
            if p=="/feedback":
                f=self.form(); turn_id=int(f["turn_id"]); correction=f.get("correction","").strip(); memory=f.get("memory","").strip()
                if len(correction)>2000 or len(memory)>500:raise ValueError("Feedback is too long")
                app.store.save_feedback(ResponseFeedback(uuid.uuid4().hex,turn_id,"","",f["rating"],correction,datetime.now(UTC)),memory)
                self.redirect("/caregiver","Response review saved. Approved memory is now available to FRED." if memory else "Response review saved.");return
            if p.startswith("/memory/") and p.endswith("/delete"):
                memory_id=p.split("/")[2]; app.store.delete_memory(memory_id); self.redirect("/caregiver","Approved memory removed.");return
            if p=="/upload":
                if length>12_000_000:raise ValueError("File is larger than 12 MB.")
                f=_multipart(self,length); filename,kind,data=f["file"]; allowed={"image/jpeg":"jpg","image/png":"png","image/webp":"webp","audio/webm":"webm","audio/mpeg":"mp3","audio/wav":"wav"}
                if kind not in allowed or not data:raise ValueError("Choose a supported photo or audio file.")
                ident=uuid.uuid4().hex; name=f"{ident}.{allowed[kind]}";(app.media_dir/(name+".enc")).write_bytes(app.secrets.encrypt_bytes(data)); media_kind="audio" if kind.startswith("audio/") else "image";app.store.add_media(FamiliarMedia(ident,str(f["title"])[:120],"/local-media/"+name,media_kind,str(f.get("description",""))[:300]));self.redirect("/caregiver","Family media encrypted and uploaded.");return
            if p=="/data/delete":
                for path in app.media_dir.glob("*.enc"):path.unlink()
                app.store.delete_personal_data();self.redirect("/caregiver","Personal data deleted.");return
        except (KeyError,ValueError) as e:self.send_error(400,str(e));return
        self.send_error(404)
    def log_message(self,fmt,*args):print("WEB:",fmt%args)
 return Handler

def serve(data_dir="data",host="127.0.0.1",port=8080,open_browser=False,certfile=None,keyfile=None,pico_device=None):
    """Start FRED's HTTP server and the background reminder-delivery loop."""
    app=RobotApplication(Path(data_dir),pico_device);server=ThreadingHTTPServer((host,port),make_handler(app))
    if certfile and keyfile:ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(certfile,keyfile);server.socket=ctx.wrap_socket(server.socket,server_side=True)
    stop=threading.Event()
    def loop():
        while not stop.wait(1):app.scheduler.deliver_due()
    threading.Thread(target=loop,daemon=True).start()
    if open_browser:threading.Timer(.5,lambda:webbrowser.open(f'{"https" if certfile else "http"}://{host}:{port}')).start()
    print(f'FRED running at {"https" if certfile else "http"}://{host}:{port}')
    try:server.serve_forever(.5)
    except KeyboardInterrupt:pass
    finally:stop.set();server.server_close();app.pico and app.pico.close()
