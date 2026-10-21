# FRED: six-month project roadmap

**Planning window:** October 21, 2026–April 21, 2027
**Status:** Proposal for planning, not a claim that any milestone is complete. Review monthly and adjust to hardware availability, user feedback, and safety findings.

## Where the project stands

FRED is a local Python prototype with a resident app (`/app`), caregiver dashboard (`/caregiver`), expressive head display (`/head`), reminders, familiar media, guarded conversation, caregiver-reviewed memories, and SMS/webhook alert adapters. SQLite stores device data, with selected sensitive fields and uploaded media encrypted. A Pi/Pico bridge supports LEDs and switches. ROS 2 face tracking and neck control have portable tests, but the physical CM5 build and its camera, audio, displays, power, and motion path still need validation together.

The next six months should aim for **one supervised, narrow use case**: a resident can receive and acknowledge a familiar daily reminder, ask for help, and have a caregiver see what happened. Conversation, gaze, and expressive motion should support that experience; they should not be treated as evidence that care or emergency response has occurred.

## Priorities and decision rules

1. **Care and safety first.** Keep the boundaries in [SAFETY.md](SAFETY.md). Caregivers remain responsible for care decisions. Do not enable unattended alerting or head motion until their failure paths are tested.
2. **A dependable core before more features.** Reminder acknowledgement, human help, offline behavior, and recovery after reboot matter more than additional AI behaviors.
3. **Resident simplicity; caregiver clarity.** The resident sees one clear next action at a time. The caregiver sees what was scheduled, acknowledged, missed, queued, provider-accepted, delivered, or failed, without implying that an alert was read.
4. **Local by default.** Continue to support predictable offline behavior. Explain when browser speech or optional model/transcription services may send data away from the device.
5. **Measured hardware decisions.** Record exact parts and electrical ratings in [CM5_BUILD.md](CM5_BUILD.md). No servo PWM until power, mechanical travel, and stop behavior are verified.

## Month-by-month plan

| Window | Main outcome | Proposed work | Exit evidence |
| --- | --- | --- | --- |
| **Month 1 · Oct 21–Nov 20** | Repeatable CM5 bring-up | Record part numbers and power measurements; boot both LCDs; validate CSI camera, microphone, speakers, Pico, HELP/ACTION switches, and service startup. Build a boot checklist and capture failures. | [Pi startup checks](../deploy/pi5/README.md) pass after a cold reboot; recorded device identities and measurements; HELP produces a visible alert record. |
| **Month 2 · Nov 21–Dec 20** | Reliable reminder and alert loop | Select one pilot routine; test recurrence, local time/DST, quiet hours, missed/late reminders, acknowledgement, and restart recovery. Improve delivery queue persistence and caregiver status wording; test actual SMS/webhook receipt and failure. | Scenario tests plus a supervised end-to-end run show each reminder's final state and distinguish provider acceptance from human acknowledgement. |
| **Month 3 · Dec 21–Jan 20** | Accessible resident and caregiver UI | Co-design with residents and caregivers. Simplify `/app` around today's action, conversation, familiar photos, and a prominent help path. Rework `/caregiver` into clear setup, today, alerts, and review sections. Test on both real screens. | Task-based observations, readable text/contrast/touch targets, keyboard and screen-reader checks where applicable, and no critical task blocked by the interface. |
| **Month 4 · Jan 21–Feb 20** | Voice and gaze that fail safely | Evaluate an on-device wake-word and speech path; retain tap-to-speak and typing. Add audio-device diagnostics and interruption/retry behavior. Validate camera publisher and ROS 2 tracking on the CM5; keep neck PWM disabled until calibrated. | Spoken-turn tests with speaker echo, noise, network loss, and reboot; measured tracking latency and target-loss behavior; motion limits and stop test documented before actuator use. |
| **Month 5 · Feb 21–Mar 20** | Privacy, caregiver control, and pilot readiness | Add per-feature consent and an obvious pause/disable control for microphone and camera. Finish retention/export/deletion policy and encrypted backup/restore procedure. Complete threat model, hazard analysis, incident plan, and clinical/accessibility review for the narrow use case. | Consent can be withdrawn; data can be restored and deleted in a test; review documents are signed off and unresolved hazards are visible. |
| **Month 6 · Mar 21–Apr 21** | Supervised pilot decision | Run a small, consented, supervised evaluation of the narrow use case. Log failures and confusing interactions without collecting unnecessary content. Fix high-severity issues, repeat end-to-end checks, and decide whether to extend, redesign, or stop the pilot. | A written go/no-go decision cites observed completion rates, alert-chain results, accessibility findings, incidents, and open risks. |

These are targets, not a commitment to deploy. If an exit gate fails, carry that work forward before adding the next dependent feature.

## Product and UI upgrades

### Resident screen and head display

- Make the current reminder the primary focus with large **Done** and **I need help** actions, a clear repeat/snooze choice only if caregiver-approved, and a visible state after each tap. Avoid piling up multiple competing prompts.
- Use short, familiar language and show the same state on `/app`, `/head`, and the LED ring. Add a visible microphone/camera status and a clear way to stop listening or tracking.
- Keep text entry and tap-to-speak available when hands-free recognition fails. Show the recognized words before acting on uncertain or safety-sensitive input.
- Respect reduced motion and avoid expression changes that suggest FRED has understood, promised, or completed something it has not.

### Caregiver workspace

- Make initial setup a guided flow: consent, profile, contacts, quiet hours, test alert, then one reminder. Surface missing setup items before enabling notification-dependent workflows.
- Show a timeline for each reminder and alert. Label `queued`, `retrying`, `provider accepted`, `delivery confirmed` (only when a callback proves it), `failed`, and `caregiver acknowledged` separately.
- Add contact test, edit/disable, and escalation-order controls; show device health and the last successful check without turning it into a false assurance of safety.
- Keep response review and approved memories understandable: source, approval date, delete control, and clear separation between a resident statement and a verified caregiver fact.

## Feature and technical decisions

| Area | Proposed decision or code change | Why / gate |
| --- | --- | --- |
| Web app | Split the large [`web.py`](../src/dementia_care_robot/web.py) into route handlers, page templates, API validation, and app services while preserving existing URLs. Move large inline scripts/styles into packaged assets. | Makes UI and security changes reviewable; keep route and integration tests green during extraction. |
| Data | Add versioned SQLite migrations and explicit event records for reminder and alert transitions in [`storage.py`](../src/dementia_care_robot/storage.py). Store timezone with caregiver-entered schedules. | Safer upgrades and accurate audit/history through DST and reboot. Test migration from an existing prototype database. |
| Notifications | Make the retry queue restart-safe in [`notifications.py`](../src/dementia_care_robot/notifications.py); add idempotency, acknowledgement timeout, and a tested fallback contact path. Review callback authentication and credential handling before a pilot. | Current background threads and provider-accepted state do not prove a human received the alert. Test provider errors, duplicate callbacks, reboot, and loss of network. |
| Voice | Put capture, wake detection, transcription, and speech playback behind clear interfaces in [`speech.py`](../src/dementia_care_robot/speech.py) and the client scripts. Evaluate local models on the actual Pi before selecting one. | Browser wake recognition may use a remote provider; `--offline` does not make it on-device. Keep manual controls as fallback. |
| Motion | Maintain one owner for neck commands; calibrate both axes in [`firmware/pico/main.py`](../firmware/pico/main.py) and connect ROS output only through a limit-enforcing serial adapter. Add watchdog/stop behavior and independent emergency stop. | ROS currently emits commands without measured servo feedback. Physical validation precedes PWM enablement. |
| Privacy/security | Add explicit consent records, retention settings, delete/export verification, and backup/restore of the database **and** device key. Threat-model resident endpoints, local network access, session handling, uploads, and external APIs. | Encryption at rest alone does not cover device loss, network exposure, or lost keys. |
| Quality | Keep unit tests for domain rules; add integration tests for migrations, HTTP permissions, reboot recovery, notification callbacks, and the full reminder/help path. Add an on-device acceptance script and record latency/CPU/temperature under simultaneous voice and tracking. | Portable tests do not establish that the assembled robot works reliably. |

Avoid committing to customer accounts, purchase verification, remote fleet management, autonomous navigation, or medical claims during this window. Revisit them only after the narrow pilot demonstrates a need and the security/regulatory work supports them. The public website should accurately distinguish the working software from concept imagery and unverified hardware capabilities.

## Evidence to collect each month

- **Experience:** Can a resident complete the reminder/help task with minimal prompting? Which words, sounds, and screen states cause confusion or distress?
- **Reliability:** Reminder delivery/acknowledgement rates, alert-chain outcomes, reboot recovery, audio failures, and time spent offline. Define denominators and log failures as well as successes.
- **Performance:** Spoken-turn response time; camera-to-display and camera-to-neck p50/p95/p99 latency; dropped frames, Pi temperature, and CPU load on the actual image.
- **Safety/privacy:** Consent withdrawals, false or missed escalation cases, motion stop tests, unexpected recording/transmission, deletion and restore checks, and incidents.

Review these with the caregiver and appropriate clinical/accessibility advisers. Do not use model fluency or a successful provider API response as a proxy for resident benefit or caregiver receipt.

## Monthly review template

At the end of each window, record: **completed evidence**, **open defects and hazards**, **what residents/caregivers reported**, **decisions made**, **scope moved to the next month**, and **who owns the next test**. Link issue IDs, test reports, and build measurements here as they are created. Keep [SAFETY.md](SAFETY.md), [HARDWARE.md](HARDWARE.md), and the deployment guide aligned with any decision that changes real-world operation.
