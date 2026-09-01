# Dementia Care Robot

An early, safety-first software foundation for an assistive robot supporting people living with dementia and their caregivers.

This repository now provides a working, hardware-neutral Python prototype for:

- caregiver- or patient-scheduled reminders with SQLite persistence;
- a familiar-photo display;
- guarded, history-aware conversation with a local fallback or optional remote LLM;
- simple wellbeing check-ins;
- caregiver escalation based on explicit safety rules;
- auditable interaction records with minimal personal data;
- replaceable speech, sensor, and notification adapters.

It is **not a medical device or emergency service**. It must not diagnose, recommend medication changes, restrain a person, impersonate a human, or replace professional care. Production use requires clinical, accessibility, privacy, security, and regulatory review.

## Quick start

Python 3.11+ is sufficient; the starter has no runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
dementia-care-robot demo
dementia-care-robot web --open
python -m unittest discover -s tests -v
```

Open `http://127.0.0.1:8080` if the browser does not open automatically. The dashboard lets you schedule reminders, add familiar images by URL, and talk or type to FRED. Data is stored under `data/`, which is ignored by Git. The console acts as the current caregiver notification hardware.

## Optional LLM conversation

Without configuration, conversation uses a predictable local fallback so the model works offline. To use an OpenAI-compatible chat-completions endpoint, set:

```bash
export ROBOT_LLM_API_KEY="your-key"
export ROBOT_LLM_MODEL="gpt-4.1-mini"       # optional
export ROBOT_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"  # optional
export ROBOT_TRANSCRIPTION_MODEL="whisper-1" # optional
dementia-care-robot web
```

Press and hold **Hold to talk**, speak, and release. The browser sends that single clip to the local server, which transcribes it, safety-checks the text, generates a response, and returns it to the tablet. The tablet displays both sides and reads FRED's response aloud. There is no always-on recording.

Conversation text and recorded clips are sent to the configured provider only when `ROBOT_LLM_API_KEY` is present. Audio is not saved locally, but the transcript is retained in the local conversation history until **Clear private conversation** is pressed. Explicit danger or distress is screened before the conversation model call; urgent messages use a fixed safety response. Model/network failures fall back locally. For a real deployment, replace environment-variable API keys with a device secret store and obtain explicit consent before sending data remotely.

## Display on a tablet

For visual testing on the same computer, `dementia-care-robot web --open` is sufficient. To serve the interface to a tablet on the same trusted Wi-Fi network:

```bash
dementia-care-robot web --host 0.0.0.0 --port 8443 \
  --certfile /path/to/trusted-certificate.pem \
  --keyfile /path/to/private-key.pem
```

Then open `https://DEVICE_IP:8443` on the tablet and allow microphone access. Modern browsers require a secure HTTPS context for microphone capture from another device. The certificate must be trusted by the tablet. This prototype does not authenticate users, so do not expose the server to the public internet or an untrusted network.

## Architecture

```text
browser / speech / buttons / sensors
          |
          v
 web app / scheduler ----> SQLiteStore
          |                    |
          v                    v
 CareCoordinator ------> SafetyPolicy
     |       |                 |
     v       v                 v
 Speaker  CaregiverNotifier  LLM adapter
```

The domain layer contains care behavior, while protocol interfaces in `ports.py` isolate vendor-specific hardware. A Raspberry Pi or robot controller can implement `Speaker`, `MediaDisplay`, and `CaregiverNotifier`; buttons and sensors can call the same coordinator and scheduler methods used by the web interface.

## Current prototype limitations

- “Caregiver notification” prints to the console and is not a reliable alert. Spoken conversation responses use the tablet browser's installed voice.
- Photo URLs may disclose the viewer's IP to the image host. Local upload/copy support is the next privacy milestone.
- The web server is intentionally bound to localhost with no authentication. Do not expose it to a network.
- Reminders are one-time only and use the device's local timezone at entry.
- SQLite is not encrypted. Do not store sensitive health data in this prototype.

## Suggested next milestones

1. Co-design conversation flows with people living with dementia and caregivers.
2. Choose one narrow pilot use case, such as hydration reminders.
3. Add explicit consent, identity, quiet-hours, recurring reminders, and caregiver-contact configuration.
4. Add authenticated local media upload plus encrypted persistence, retention, and deletion controls.
5. Implement GPIO adapters for a physical help button, speaker, and status light, with a fail-safe notification service.
6. Add robot-speaker text-to-speech behind the existing port, then run accessibility, failure-mode, and supervised usability testing.

See [docs/SAFETY.md](docs/SAFETY.md) before connecting sensors, language models, health records, or physical actuators.
