"""SQLite persistence with encryption at the boundary for personal fields."""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from .models import (AlertDelivery, ApprovedMemory, CareProfile, CaregiverContact,
                     ConversationTurn, FamiliarMedia, Reminder, ReminderStatus,
                     ResponseFeedback, RiskLevel)
from .security import DeviceSecrets


class SQLiteStore:
    """SQLite metadata with authenticated field encryption for personal content."""
    def __init__(self, path: str | Path = "robot.db", secrets: DeviceSecrets | None = None) -> None:
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.secrets = str(path), secrets or DeviceSecrets(path.parent)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10); db.row_factory = sqlite3.Row; return db

    @contextmanager
    def _database(self):
        db = self._connect()
        try:
            with db: yield db
        finally: db.close()

    def _initialize(self) -> None:
        """Create the current schema and apply small upgrades to older databases."""
        with self._database() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY,message TEXT NOT NULL,due_at TEXT NOT NULL,delivered_at TEXT,recurrence TEXT NOT NULL DEFAULT 'none',status TEXT NOT NULL DEFAULT 'scheduled',occurrence_at TEXT,acknowledged_at TEXT,voice_note_uri TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS reminder_events(id INTEGER PRIMARY KEY AUTOINCREMENT,reminder_id TEXT NOT NULL,occurrence_at TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY,title TEXT NOT NULL,uri TEXT NOT NULL,kind TEXT NOT NULL,description TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversation(id INTEGER PRIMARY KEY AUTOINCREMENT,role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS response_feedback(id TEXT PRIMARY KEY,assistant_turn_id INTEGER NOT NULL UNIQUE,prompt TEXT NOT NULL,response TEXT NOT NULL,rating TEXT NOT NULL,correction TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(assistant_turn_id) REFERENCES conversation(id));
            CREATE TABLE IF NOT EXISTS approved_memories(id TEXT PRIMARY KEY,content TEXT NOT NULL,source_feedback_id TEXT,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS care_profile(id INTEGER PRIMARY KEY CHECK(id=1),preferred_name TEXT NOT NULL,important_people TEXT NOT NULL,interests TEXT NOT NULL,daily_routine TEXT NOT NULL,comforts TEXT NOT NULL,usual_item_locations TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS caregiver_contacts(id TEXT PRIMARY KEY,name TEXT NOT NULL,channel TEXT NOT NULL,destination TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS alert_deliveries(id TEXT PRIMARY KEY,contact_id TEXT NOT NULL,reason TEXT NOT NULL,risk TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,provider_id TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS health_events(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,value TEXT NOT NULL,created_at TEXT NOT NULL);
            """)
            # These additive migrations let early prototype databases keep working.
            cols = {r[1] for r in db.execute("PRAGMA table_info(reminders)")}
            for name, definition in {"recurrence":"TEXT NOT NULL DEFAULT 'none'","status":"TEXT NOT NULL DEFAULT 'scheduled'","occurrence_at":"TEXT","acknowledged_at":"TEXT","voice_note_uri":"TEXT NOT NULL DEFAULT ''"}.items():
                if name not in cols: db.execute(f"ALTER TABLE reminders ADD COLUMN {name} {definition}")
            db.execute("UPDATE reminders SET status='delivered' WHERE delivered_at IS NOT NULL AND status='scheduled'")

    def _reminder(self, r):
        """Turn one database row into a decrypted domain object."""
        return Reminder(r["id"],self.secrets.decrypt(r["message"]),datetime.fromisoformat(r["due_at"]),r["recurrence"],ReminderStatus(r["status"]),datetime.fromisoformat(r["occurrence_at"]) if r["occurrence_at"] else None,r["voice_note_uri"])
    def add_reminder(self, x: Reminder) -> None:
        with self._database() as db: db.execute("INSERT INTO reminders(id,message,due_at,recurrence,status,voice_note_uri) VALUES(?,?,?,?,?,?)",(x.reminder_id,self.secrets.encrypt(x.message),x.due_at.astimezone(UTC).isoformat(),x.recurrence,x.status.value,x.voice_note_uri))
    def list_reminders(self, include_delivered=False):
        q="SELECT * FROM reminders"+("" if include_delivered else " WHERE status='scheduled'")+" ORDER BY due_at"
        with self._database() as db: return [self._reminder(r) for r in db.execute(q)]
    def due_reminders(self, now):
        with self._database() as db: return [self._reminder(r) for r in db.execute("SELECT * FROM reminders WHERE status='scheduled' AND due_at<=? ORDER BY due_at",(now.astimezone(UTC).isoformat(),))]
    def mark_delivered(self, reminder_id, at, next_due=None):
        stamp=at.astimezone(UTC).isoformat()
        with self._database() as db:
            db.execute("UPDATE reminders SET delivered_at=?,occurrence_at=?,status='delivered' WHERE id=?",(stamp,stamp,reminder_id)); db.execute("INSERT INTO reminder_events(reminder_id,occurrence_at,status,created_at) VALUES(?,?,'delivered',?)",(reminder_id,stamp,stamp))
            if next_due: db.execute("UPDATE reminders SET due_at=? WHERE id=?",(next_due.astimezone(UTC).isoformat(),reminder_id))
    def acknowledge_reminder(self, reminder_id, status, at):
        if status not in {ReminderStatus.ACKNOWLEDGED,ReminderStatus.NEEDS_HELP,ReminderStatus.MISSED}: raise ValueError("Invalid acknowledgement")
        stamp=at.astimezone(UTC).isoformat()
        with self._database() as db:
            row=db.execute("SELECT occurrence_at,recurrence FROM reminders WHERE id=?",(reminder_id,)).fetchone()
            if not row:return False
            next_status=ReminderStatus.SCHEDULED.value if row["recurrence"]!="none" else status.value
            db.execute("UPDATE reminders SET status=?,acknowledged_at=? WHERE id=?",(next_status,stamp,reminder_id)); db.execute("INSERT INTO reminder_events(reminder_id,occurrence_at,status,created_at) VALUES(?,?,?,?)",(reminder_id,row[0] or stamp,status.value,stamp))
        return True
    def daily_summary(self, day=None):
        day=day or datetime.now().astimezone().date(); start=datetime.combine(day,datetime.min.time()).astimezone().astimezone(UTC); end=start.replace(hour=23,minute=59,second=59)
        with self._database() as db:
            counts={r["status"]:r["count"] for r in db.execute("SELECT status,COUNT(*) count FROM reminder_events WHERE created_at BETWEEN ? AND ? GROUP BY status",(start.isoformat(),end.isoformat()))}; counts["alerts"]=db.execute("SELECT COUNT(*) FROM alert_deliveries WHERE created_at BETWEEN ? AND ?",(start.isoformat(),end.isoformat())).fetchone()[0]
        return counts
    def add_media(self,x):
        with self._database() as db: db.execute("INSERT OR REPLACE INTO media VALUES(?,?,?,?,?)",(x.media_id,self.secrets.encrypt(x.title),x.uri,x.kind,self.secrets.encrypt(x.description)))
    def list_media(self):
        with self._database() as db: rows=list(db.execute("SELECT * FROM media ORDER BY id"))
        return [FamiliarMedia(r["id"],self.secrets.decrypt(r["title"]),r["uri"],r["kind"],self.secrets.decrypt(r["description"])) for r in rows]
    def append_turn(self,x):
        with self._database() as db:
            cursor=db.execute("INSERT INTO conversation(role,content,created_at) VALUES(?,?,?)",(x.role,self.secrets.encrypt(x.content),x.at.isoformat()))
            return cursor.lastrowid
    def conversation(self,limit=12):
        with self._database() as db: rows=list(db.execute("SELECT id,role,content,created_at FROM conversation ORDER BY id DESC LIMIT ?",(limit,)))
        return [ConversationTurn(r["role"],self.secrets.decrypt(r["content"]),datetime.fromisoformat(r["created_at"]),r["id"]) for r in reversed(rows)]
    def conversation_pairs(self,limit=10):
        # Pair each assistant turn with the closest preceding user turn so the
        # caregiver reviews exactly the exchange that produced the response.
        with self._database() as db:
            rows=list(db.execute("""SELECT a.id assistant_turn_id,u.content prompt,a.content response,a.created_at,
                f.rating FROM conversation a JOIN conversation u ON u.id=(SELECT MAX(id) FROM conversation WHERE id<a.id AND role='user')
                LEFT JOIN response_feedback f ON f.assistant_turn_id=a.id WHERE a.role='assistant' ORDER BY a.id DESC LIMIT ?""",(limit,)))
        return [{"assistant_turn_id":r["assistant_turn_id"],"prompt":self.secrets.decrypt(r["prompt"]),"response":self.secrets.decrypt(r["response"]),"created_at":datetime.fromisoformat(r["created_at"]),"rating":r["rating"] or ""} for r in rows]
    def save_feedback(self,feedback,memory=""):
        # Prompt and response are read from the database instead of trusting
        # browser-submitted copies, which could have been modified by a client.
        if feedback.rating not in {"helpful","confusing","unsafe"}:raise ValueError("Invalid feedback rating")
        with self._database() as db:
            row=db.execute("""SELECT a.role,a.content response,(SELECT content FROM conversation WHERE id<a.id AND role='user' ORDER BY id DESC LIMIT 1) prompt
                FROM conversation a WHERE a.id=?""",(feedback.assistant_turn_id,)).fetchone()
            if not row or row["role"]!="assistant" or row["prompt"] is None:raise ValueError("Conversation response not found")
            db.execute("INSERT OR REPLACE INTO response_feedback VALUES(?,?,?,?,?,?,?)",(feedback.feedback_id,feedback.assistant_turn_id,row["prompt"],row["response"],feedback.rating,self.secrets.encrypt(feedback.correction),feedback.created_at.isoformat()))
            if memory.strip():db.execute("INSERT INTO approved_memories VALUES(?,?,?,?)",(feedback.feedback_id,self.secrets.encrypt(memory.strip()),feedback.feedback_id,feedback.created_at.isoformat()))
    def feedback(self):
        with self._database() as db:rows=list(db.execute("SELECT * FROM response_feedback ORDER BY created_at"))
        return [ResponseFeedback(r["id"],r["assistant_turn_id"],self.secrets.decrypt(r["prompt"]),self.secrets.decrypt(r["response"]),r["rating"],self.secrets.decrypt(r["correction"]),datetime.fromisoformat(r["created_at"])) for r in rows]
    def approved_memories(self):
        with self._database() as db:rows=list(db.execute("SELECT * FROM approved_memories ORDER BY created_at"))
        return [ApprovedMemory(r["id"],self.secrets.decrypt(r["content"]),datetime.fromisoformat(r["created_at"])) for r in rows]
    def delete_memory(self,memory_id):
        with self._database() as db:return db.execute("DELETE FROM approved_memories WHERE id=?",(memory_id,)).rowcount>0
    def clear_conversation(self):
        with self._database() as db: db.execute("DELETE FROM conversation")
    def save_care_profile(self,p):
        vals=[self.secrets.encrypt(v) for v in (p.preferred_name,p.important_people,p.interests,p.daily_routine,p.comforts,p.usual_item_locations)]
        with self._database() as db: db.execute("INSERT OR REPLACE INTO care_profile VALUES(1,?,?,?,?,?,?)",vals)
    def care_profile(self):
        with self._database() as db:r=db.execute("SELECT * FROM care_profile WHERE id=1").fetchone()
        return CareProfile() if not r else CareProfile(*(self.secrets.decrypt(r[k]) for k in ("preferred_name","important_people","interests","daily_routine","comforts","usual_item_locations")))
    def setting(self,key,default=""):
        with self._database() as db:r=db.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return self.secrets.decrypt(r[0]) if r else default
    def set_setting(self,key,value):
        with self._database() as db:db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(key,self.secrets.encrypt(value)))
    def configured(self):return bool(self.setting("caregiver_password_hash"))
    def add_contact(self,x):
        with self._database() as db:db.execute("INSERT OR REPLACE INTO caregiver_contacts VALUES(?,?,?,?,?)",(x.contact_id,self.secrets.encrypt(x.name),x.channel,self.secrets.encrypt(x.destination),int(x.enabled)))
    def contacts(self):
        with self._database() as db:rows=list(db.execute("SELECT * FROM caregiver_contacts WHERE enabled=1"))
        return [CaregiverContact(r["id"],self.secrets.decrypt(r["name"]),r["channel"],self.secrets.decrypt(r["destination"]),bool(r["enabled"])) for r in rows]
    def save_delivery(self,x):
        with self._database() as db:db.execute("INSERT OR REPLACE INTO alert_deliveries VALUES(?,?,?,?,?,?,?,?,?)",(x.delivery_id,x.contact_id,self.secrets.encrypt(x.reason),x.risk.value,x.status,x.attempts,x.created_at.isoformat(),x.updated_at.isoformat(),x.provider_id))
    def deliveries(self,limit=20):
        with self._database() as db:rows=list(db.execute("SELECT * FROM alert_deliveries ORDER BY created_at DESC LIMIT ?",(limit,)))
        return [AlertDelivery(r["id"],r["contact_id"],self.secrets.decrypt(r["reason"]),RiskLevel(r["risk"]),r["status"],r["attempts"],datetime.fromisoformat(r["created_at"]),datetime.fromisoformat(r["updated_at"]),r["provider_id"]) for r in rows]
    def update_delivery_status(self,provider_id,status):
        allowed={"queued","sent","delivered","undelivered","failed","read"}
        if status not in allowed:return False
        with self._database() as db:
            cursor=db.execute("UPDATE alert_deliveries SET status=?,updated_at=? WHERE provider_id=?",(status,datetime.now(UTC).isoformat(),provider_id))
            return cursor.rowcount>0
    def record_health(self,kind,value,at=None):
        with self._database() as db:db.execute("INSERT INTO health_events(kind,value,created_at) VALUES(?,?,?)",(kind,value,(at or datetime.now(UTC)).isoformat()))
    def last_health(self,kind):
        with self._database() as db:r=db.execute("SELECT created_at FROM health_events WHERE kind=? ORDER BY id DESC LIMIT 1",(kind,)).fetchone()
        return datetime.fromisoformat(r[0]) if r else None
    def delete_personal_data(self):
        with self._database() as db:db.executescript("DELETE FROM response_feedback;DELETE FROM approved_memories;DELETE FROM conversation;DELETE FROM media;DELETE FROM care_profile;DELETE FROM reminders;DELETE FROM reminder_events;DELETE FROM caregiver_contacts;DELETE FROM alert_deliveries;")
