# FRED 2.0 — HumanFrame Application

**Native HumanFrame app ID:** `fred-companion`  
**Version:** `0.2.0`  
**Runtime app port:** `8000`  
**Entry point:** `app.py`  
**HumanFrame SDK:** installed by the robot-side `humanframe-deploy` tool.

This conversion replaces FRED's **standalone Pi systemd lifecycle** with the **HumanFrame Runtime** application lifecycle. The uploaded application must be run under HumanFrame, not installed as a second `fred.service`.

## What was adapted

- Added the manifest required by HumanFrame Platform's `HumanFrame Runtime / CM5` backend and the robot's deployer.
- Added an `app.py` entry point that reads the manifest port and serves the app on `127.0.0.1`, supplies `/health`, and leaves boot/restart/rollback to the Runtime.
- Served the expressive head at **`/`** (also `/head`), companion and conversation UI at `/app`, caregiver workspace at `/caregiver`, activities at `/activities`, and the original introductory site at `/home`.
- Combined FRED's previously separate HTTP head and body servers into **one** managed app port. The optional second display is **not** automatically launched by HumanFrame Core.
- Added `HumanFrameIntegration`, which uses the installed `humanframe.HumanFrame` SDK to retrieve Runtime status and record an explicitly requested 1–10 second WAV from the robot microphone. If a transcription API key is configured, `/app` offers a robot microphone button. Audio is deleted after the local app reads it.
- The optional legacy Pico serial bridge is disabled by default. The current SDK does **not** provide Pico neck/LED control; do not claim this is SDK-managed.
- Caregiver authentication is enabled for HumanFrame deployments. The encrypted SQLite data and media live outside versioned app directories and survive an upgrade.

## Package contents

Upload the **deployment ZIP** supplied with this source; it must have `humanframe.json`, `app.py`, `requirements.txt`, `src/`, and `pyproject.toml` at its root, not wrapped in an extra repository directory.

`requirements.txt` deliberately installs only application dependencies. **Do not change it to `-e .`** for the robot-side deployment: the present deployer invokes pip with the requirements file path but does not set its current working directory to the deployed application. `app.py` adds `src/` to Python's import path; `humanframe-deploy` installs the HumanFrame SDK in the application venv separately.

## Deploy from HumanFrame Platform

1. Confirm the physical CM5 has reliable power and Wi-Fi. It previously showed an undervoltage warning; do not install packages while power is unstable.
2. SSH to the Pi and verify `systemctl is-active humanframe-runtime`, `command -v humanframe-deploy`, and `curl -fsS http://127.0.0.1:7000/__humanframe/status`.
3. Record the **previous active application** using `readlink -f /opt/humanframe/current`, and back up app data/configuration before the first deployment. Successful deployment will replace the active app.
4. Start HumanFrame Platform locally and choose **HumanFrame Runtime / CM5**, the **physical CM5 IP**, **SSH port 22**, and its real SSH user (`ffred` on the lab robot). Do not select the Docker simulator at `127.0.0.1:2222`.
5. Upload `fred-companion-humanframe-0.2.0.zip` via **Applications > Upload**; deploy to the CM5. The deployer owns environment creation, SDK installation, activation, health check, and rollback. The new version is unique, so it won't conflict with a previously installed `fred-companion` version.
6. Verify on the Pi:

   ```sh
   systemctl is-active humanframe-runtime
   curl -fsS http://127.0.0.1:7000/__humanframe/status
   curl -fsS http://127.0.0.1:8000/health
   readlink -f /opt/humanframe/current
   tail -n 60 /opt/humanframe/logs/application.log
   ```

7. Check the Pi's physical Chromium launcher. This package displays the **head at `http://127.0.0.1:8000/`**. If `launch-display.sh` still points at simulator-only port `8081`, update its URL **only after** confirming `/health` and `/` respond on 8000. Preserve a launcher backup.
8. In the Platform preview, open `/` for the face and `/app` for the resident interface. `/caregiver` requests onboarding/password on first use.

**Physical deployment is not yet verified by these local tests.** A successful Simulator deployment does not establish that the Pi's currently installed deployer can restart systemd; the simulator uses Supervisor. If `humanframe-deploy` invokes `supervisorctl` on this physical robot but the real Runtime service is `systemd`, fix the deployer/backend mismatch **in Core and provisioning**, not in FRED's app ZIP. Avoid manually replacing live Core files without a backup and rollback plan.

## Persistent data and credentials

Default data directory (requires permissions for the Runtime user):

```text
/opt/humanframe/data/fred-companion/
    robot.db             # encrypted personal data / metadata
    secret.key (or equivalent generated keys)
    media/               # encrypted uploaded media
    fred.env             # optional device-side ROBOT_* settings; never package this
```

The exact key file names are determined by `DeviceSecrets`. Back up the entire directory, not only the database. For an online demo, create `fred.env` **directly on the robot**, using the source `.env.example` as reference, and set permissions to owner-only:

```sh
chmod 600 /opt/humanframe/data/fred-companion/fred.env
```

Example values (do not commit actual keys):

```text
ROBOT_LLM_API_KEY=replace-with-real-key-on-device
ROBOT_LLM_MODEL=gpt-4.1-mini
```

Without a key FRED uses its existing **offline fallback companion**. Remote transcription, conversation model calls, and SMS delivery require their own configured providers, permissions, and consent. This demo is not a medical device or a substitute for caregivers or emergency services. Treat data uploaded to FRED as sensitive.

Existing data stored by the old standalone FRED service (for example `/var/lib/fred`) is **not migrated automatically**. Back up and migrate it separately; don't overwrite an encrypted DB without its matching keys.

## Supported SDK boundary

| Capability | Current integration |
| --- | --- |
| App lifecycle | **HumanFrame Runtime** supervises and restarts the process |
| Health | `GET /health`, consumed by the Runtime's supervisor |
| Runtime state | `HumanFrame().status()` via `GET /api/humanframe/status` |
| Robot microphone | `HumanFrame().audio.record(duration=3)` via an **explicit** user action at `/app`, only when transcription is configured |
| Camera | SDK has **snapshot** `camera.capture()`; FRED's live browser gaze currently uses `getUserMedia`, not a Runtime video stream |
| Speech playback | Existing Chromium/browser speech synthesis, **not** an SDK speaker method |
| Neck/LED/Pico | Existing direct serial integration, disabled unless `ROBOT_PICO_DEVICE` is explicitly set; the HumanFrame SDK currently has no matching motor/LED API |
| Second physical display | **Not managed** by this one-port HumanFrame application; needs a HumanFrame Core display contract or separate supported launcher |

## Developer handoff: required rules for future FRED releases

- Implement all physical robot capabilities through **existing supported HumanFrame SDK APIs**, adding new APIs to Core first where needed; don't bundle a separate competing Runtime, robot server/service, or deployer.
- Keep `humanframe.json` schema 1, valid app ID/version, valid entry point, supported permissions, and an actual `/health` endpoint.
- Honor the manifest port. Do not hardcode an unrelated second mandatory server or bind the app to a public network interface.
- For every release, increment `humanframe.json.version`; installed ID/version pairs cannot be overwritten by the robot deployer.
- Put private data and keys outside the versioned code directory. Never package `.env`, database files, private images/recordings, or device tokens.
- Never assume simulator-only ports (`8081`, `2222`) exist on the CM5.
- Test in the simulator, then complete a physical acceptance test **with backup and rollback**. Test CPU, memory, power, display, camera, microphone and network conditions separately.
- The original `deploy/fred.service`, `deploy/pi5/start-displays.sh`, ROS2, Pico firmware, and marketing files in the source repository are **legacy/independent** and are not part of the deployment ZIP.

## Local developer verification

From the full source project, if you have the HumanFrame SDK available on your Python path:

```sh
FRED_DATA_DIR=/tmp/fred-humanframe-test ROBOT_OFFLINE_MODE=1 python app.py
curl -fsS http://127.0.0.1:8000/health
```

Use a temporary data directory and an unused port in the manifest when testing locally; the provided manifest uses 8000 to fit the lab CM5 display launcher. Run project tests with `PYTHONPATH=src python -m pytest -q tests`. The original reminder tests assume a non-quiet local time; their result can be time-of-day dependent.
