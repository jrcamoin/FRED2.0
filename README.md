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

## Caregiver setup and Raspberry Pi deployment

Open `/caregiver` to schedule reminders, upload familiar media, and configure contacts. Caregiver authentication is temporarily disabled for local prototyping; the preserved onboarding, login, and session code can be restored by setting `CAREGIVER_AUTH_ENABLED = True` in `web.py`.

Personal profile text, conversations, contact destinations, reminder messages, photos, and voice notes are encrypted at rest using a device key stored at `data/.device-key` with owner-only permissions. Back up that key separately: encrypted data cannot be recovered without it. For production, also enable Raspberry Pi OS full-disk encryption, HTTPS, firewalling, automatic security updates, and physical protection of the SD card.

For SMS alerts, configure the three required `ROBOT_TWILIO_*` settings shown in `.env.example`. Push contacts accept an HTTPS endpoint receiving `{title, message}` JSON. Provider acceptance, retries, and failures appear on the caregiver dashboard. To receive carrier delivery status, expose the callback over HTTPS and configure the optional callback URL and a long random callback token. Neither channel is an emergency service.

## Quick start

The Human Frame Robotics website opens at `http://localhost:8080/`.
The saved `HumanFrameRoboticsWebsite` is integrated as the main brand site.
The FRED product website is retained at `/fred`, linked from the main navigation
and a dedicated feature section. Both sites link to the companion and caregiver
spaces, with matching responsive styling. Public assets ship inside the Python
package under `static/site`; no separate frontend server is needed.

Choose **Open your robot** to enter FRED at `/app`; caregiver tools remain at
`/caregiver`. Customer login is not implemented yet: preview access goes
directly into this server's robot app. Future customer accounts will need
purchase verification and a mapping from each customer to their own device;
the existing caregiver password is not a customer account system.

Python 3.11+ is required. The only runtime package is `cryptography`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
dementia-care-robot demo
dementia-care-robot web --open
python -m unittest discover -s tests -v
```

Open `http://127.0.0.1:8080` if the browser does not open automatically. The dashboard lets you schedule reminders, add familiar images by URL, create a caregiver-provided Care Profile, and talk or type to FRED. Profile details such as routines, comforting interests, and usual item locations are used when relevant so FRED can give more familiar, practical answers. Data is stored under `data/`, which is ignored by Git. The console acts as the current caregiver notification hardware.

### Linux setup

On Debian, Ubuntu, or Raspberry Pi OS, install Python's virtual-environment support first:

```bash
sudo apt update
sudo apt install python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
dementia-care-robot web --open
```

Desktop Linux users need a browser with microphone permission. Raspberry Pi hardware checks also use `alsa-utils`; install it with `sudo apt install alsa-utils`. USB Pico access normally requires membership in the `dialout` group. The GitHub Actions workflow runs the complete test suite on Ubuntu with Python 3.11, 3.12, and 3.13 for every push and pull request.

## Optional LLM conversation

Without configuration, conversation uses a predictable local fallback so the model works offline. To enable generated chat and voice transcription, copy the example configuration once:

```bash
cp .env.example .env
# Open .env and replace your-api-key-here with your actual API key.
dementia-care-robot web
```

The local `.env` file is loaded automatically and ignored by Git. Values already exported in the shell take priority. The model and endpoint settings in `.env.example` are optional defaults.

To test without making any paid API calls, keep the saved key and explicitly start in offline mode:

```bash
dementia-care-robot web --offline
```

For generated replies without API charges, run the installed Ollama service and use local AI mode:

```bash
ollama serve
dementia-care-robot web --local-ai
```

Local AI mode defaults to `llama3.2:3b`. Override it with `ROBOT_LOCAL_MODEL` when another Ollama model is installed. Safety screening still happens locally before the model is called.

In offline testing mode, the **Hold to speak** button uses the browser's built-in speech recognition and sends only the resulting text to the local companion. This makes no OpenAI API calls. Browser speech recognition availability and whether processing stays on-device depend on the browser and operating system.

Press and hold **Hold to talk**, speak, and release. The browser sends that single clip to the local server, which transcribes it, safety-checks the text, generates a response, and returns it to the tablet. The tablet displays both sides and reads FRED's response aloud. There is no always-on recording.

Conversation text and recorded clips are sent to the configured provider only when `ROBOT_LLM_API_KEY` is present. Audio is not saved locally, but the transcript is retained in the local conversation history until **Clear private conversation** is pressed. Explicit danger or distress is screened before the conversation model call; urgent messages use a fixed safety response. API failures are reported rather than disguised as generated replies. For a real deployment, replace the `.env` key with a device secret store and obtain explicit consent before sending data remotely.

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

## Caregiver-reviewed learning

The caregiver dashboard lists recent FRED responses for review. A caregiver can rate a response as helpful, confusing, or unsafe, provide a better answer, and optionally approve one verified fact for future conversations. Approved memories are encrypted and added only when their words overlap the resident's current question. Resident statements never become trusted memories automatically.

Reviewed examples can be exported for offline evaluation of new prompts or models. The export contains decrypted conversation text and must be handled as sensitive personal data:

```bash
dementia-care-robot export-feedback --data-dir data --output private-feedback.jsonl
```

The command creates the file with owner-only permissions. Review and de-identify it before moving it off the device or using it with an external service.

For the Raspberry Pi 3 Model B v1.2 + Pico + LCD + microphone + speakers + LED-ring build, see [docs/HARDWARE.md](docs/HARDWARE.md). Check attached devices with `dementia-care-robot hardware-check`, then start the bridge with `--pico auto`.

## Current prototype limitations

- Spoken conversation responses use the browser's installed voice. Configured SMS and push-webhook alerts still require end-to-end testing and are not an emergency service.
- Photo URLs may disclose the viewer's IP to the image host. Local upload/copy support is the next privacy milestone.
- Both resident and caregiver pages are temporarily unauthenticated for local prototyping. Do not expose the server to a public or untrusted network.
- Reminder times use the device's local timezone at entry.
- Sensitive SQLite fields and uploaded media are encrypted, but metadata and database structure are visible. Do not treat this as a substitute for full-disk encryption.

## Suggested next milestones

1. Co-design conversation flows with people living with dementia and caregivers.
2. Choose one narrow pilot use case, such as hydration reminders.
3. Add explicit consent, identity, quiet-hours, recurring reminders, and caregiver-contact configuration.
4. Add authenticated local media upload plus encrypted persistence, retention, and deletion controls.
5. Implement GPIO adapters for a physical help button, speaker, and status light, with a fail-safe notification service.
6. Add robot-speaker text-to-speech behind the existing port, then run accessibility, failure-mode, and supervised usability testing.

See [docs/SAFETY.md](docs/SAFETY.md) before connecting sensors, language models, health records, or physical actuators.
