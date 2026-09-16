"""Deliver caregiver alerts through SMS or HTTPS webhooks with retries."""

import base64
import json
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import AlertDelivery, Assessment
from .storage import SQLiteStore


class DeliveryNotifier:
    """Persistent SMS/webhook notifier with bounded background retries."""
    def __init__(self, store: SQLiteStore, retries: int = 3) -> None:
        self.store, self.retries = store, retries

    def notify(self, assessment: Assessment) -> None:
        # Network work runs in daemon threads so an unavailable provider cannot
        # freeze the resident interface or reminder scheduler.
        for contact in self.store.contacts():
            now=datetime.now(UTC); item=AlertDelivery(uuid.uuid4().hex,contact.contact_id,assessment.reason,assessment.risk,"queued",0,now,now)
            self.store.save_delivery(item)
            threading.Thread(target=self._deliver,args=(item,contact.channel,contact.destination),daemon=True).start()

    def _deliver(self, item, channel, destination):
        """Attempt delivery with short exponential backoff and persist each state."""
        last=item
        for attempt in range(1,self.retries+1):
            try:
                provider=self._send(channel,destination,f"FRED {item.risk.value.upper()} alert: {item.reason}")
                now=datetime.now(UTC); self.store.save_delivery(AlertDelivery(item.delivery_id,item.contact_id,item.reason,item.risk,"provider_accepted",attempt,item.created_at,now,provider)); return
            except Exception as error:
                now=datetime.now(UTC); last=AlertDelivery(item.delivery_id,item.contact_id,item.reason,item.risk,"retrying" if attempt<self.retries else "failed",attempt,item.created_at,now,str(error)[:120]); self.store.save_delivery(last)
                if attempt<self.retries: time.sleep(min(2**attempt,8))

    def _send(self, channel, destination, message):
        if channel == "sms":
            sid=os.environ.get("ROBOT_TWILIO_ACCOUNT_SID",""); token=os.environ.get("ROBOT_TWILIO_AUTH_TOKEN",""); sender=os.environ.get("ROBOT_TWILIO_FROM","")
            if not all((sid,token,sender)): raise RuntimeError("Twilio is not configured")
            fields={"To":destination,"From":sender,"Body":message}
            callback=os.environ.get("ROBOT_TWILIO_STATUS_CALLBACK","")
            token=os.environ.get("ROBOT_DELIVERY_CALLBACK_TOKEN","")
            if callback and token: fields["StatusCallback"]=callback+("&" if "?" in callback else "?")+"token="+token
            data=urlencode(fields).encode(); request=Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",data=data)
            request.add_header("Authorization","Basic "+base64.b64encode(f"{sid}:{token}".encode()).decode())
            with urlopen(request,timeout=15) as response: return str(json.load(response).get("sid",""))
        if channel == "push":
            request=Request(destination,data=json.dumps({"title":"FRED caregiver alert","message":message}).encode(),headers={"Content-Type":"application/json"})
            with urlopen(request,timeout=15) as response: return response.headers.get("X-Request-Id",str(response.status))
        raise ValueError("Unsupported notification channel")
