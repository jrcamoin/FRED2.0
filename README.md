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

Open `http://127.0.0.1:8080` if the browser does not open automatically. The dashboard lets you schedule reminders, add familiar images by URL, and have a simple conversation. Data is stored under `data/`, which is ignored by Git. The console acts as the current speaker and caregiver notification hardware.

## Optional LLM conversation

Without configuration, conversation uses a predictable local fallback so the model works offline. To use an OpenAI-compatible chat-completions endpoint, set:

```bash
export ROBOT_LLM_API_KEY="your-key"
export ROBOT_LLM_MODEL="gpt-4.1-mini"       # optional
export ROBOT_LLM_ENDPOINT="https://api.openai.com/v1/chat/completions"  # optional
dementia-care-robot web
```

Conversation text is sent to the configured provider only when `ROBOT_LLM_API_KEY` is present. Explicit danger or distress is screened before the model call; urgent messages use a fixed safety response. Model/network failures fall back locally. For a real deployment, replace API keys in environment variables with a device secret store and obtain explicit consent before sending any data remotely.

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

- “Caregiver notification” and speech print to the console; they are not reliable alerts.
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
6. Add speech-to-text/text-to-speech behind the existing ports, then run accessibility, failure-mode, and supervised usability testing.

See [docs/SAFETY.md](docs/SAFETY.md) before connecting sensors, language models, health records, or physical actuators.
