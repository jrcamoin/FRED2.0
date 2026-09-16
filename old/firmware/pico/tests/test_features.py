import os
import tempfile
import unittest
from io import BytesIO
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from dementia_care_robot.api_errors import RemoteServiceError
from dementia_care_robot.config import load_dotenv
from dementia_care_robot.conversation import ConversationService, OfflineCompanion, OpenAICompatibleModel
from dementia_care_robot.coordinator import CareCoordinator
from dementia_care_robot.models import AlertDelivery, CareProfile, CaregiverContact, FamiliarMedia, Reminder, ReminderStatus, RiskLevel
from dementia_care_robot.security import DeviceSecrets
from dementia_care_robot.hardware import PicoBridge
from dementia_care_robot.scheduler import ReminderScheduler
from dementia_care_robot.storage import SQLiteStore
from dementia_care_robot.speech import OpenAITranscriber
from dementia_care_robot.web import RobotApplication, _page


class FakeSpeaker:
    def __init__(self): self.messages = []
    def say(self, message): self.messages.append(message)


class FakeNotifier:
    def __init__(self): self.assessments = []
    def notify(self, assessment): self.assessments.append(assessment)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.temp.name) / "test.db")
        self.speaker, self.notifier = FakeSpeaker(), FakeNotifier()

    def tearDown(self): self.temp.cleanup()

    def test_due_reminders_deliver_once(self):
        scheduler = ReminderScheduler(self.store, CareCoordinator(self.speaker, self.notifier))
        now = datetime.now(UTC)
        scheduler.schedule(Reminder("due", "Drink water.", now - timedelta(seconds=1)))
        scheduler.schedule(Reminder("later", "Lunch time.", now + timedelta(hours=1)))
        self.assertEqual([r.reminder_id for r in scheduler.deliver_due(now)], ["due"])
        self.assertEqual(scheduler.deliver_due(now), [])
        self.assertEqual(len(self.speaker.messages), 1)

    def test_daily_reminder_waits_for_ack_then_reschedules(self):
        scheduler = ReminderScheduler(self.store, CareCoordinator(self.speaker, self.notifier))
        now = datetime.now(UTC).replace(hour=12)
        scheduler.schedule(Reminder("daily", "Drink water.", now - timedelta(minutes=1), "daily"))
        scheduler.deliver_due(now)
        current = self.store.list_reminders(True)[0]
        self.assertEqual(current.status, ReminderStatus.DELIVERED)
        self.assertTrue(self.store.acknowledge_reminder("daily", ReminderStatus.ACKNOWLEDGED, now))
        current = self.store.list_reminders()[0]
        self.assertEqual(current.status, ReminderStatus.SCHEDULED)
        self.assertGreater(current.due_at, now)

    def test_quiet_hours_hold_due_reminders(self):
        scheduler = ReminderScheduler(self.store, CareCoordinator(self.speaker, self.notifier))
        self.store.set_setting("quiet_start", "00:00")
        self.store.set_setting("quiet_end", "23:59")
        now = datetime.now(UTC)
        scheduler.schedule(Reminder("quiet", "Rest.", now - timedelta(minutes=1)))
        self.assertEqual(scheduler.deliver_due(now), [])

    def test_sensitive_fields_are_encrypted_on_disk(self):
        profile = CareProfile(preferred_name="Unique Secret Name")
        self.store.save_care_profile(profile)
        self.store.add_contact(CaregiverContact("c1", "Maya", "sms", "+15551234567"))
        raw = Path(self.store.path).read_bytes()
        self.assertNotIn(b"Unique Secret Name", raw)
        self.assertNotIn(b"+15551234567", raw)
        self.assertEqual(self.store.care_profile(), profile)

    def test_password_hash_and_session(self):
        encoded = DeviceSecrets.hash_password("a-long-password")
        self.assertTrue(DeviceSecrets.verify_password("a-long-password", encoded))
        self.assertFalse(DeviceSecrets.verify_password("wrong", encoded))
        token = self.store.secrets.issue_session()
        self.assertTrue(self.store.secrets.valid_session(token))

    def test_provider_delivery_acknowledgement_updates_record(self):
        now = datetime.now(UTC)
        delivery = AlertDelivery("d1", "c1", "Check-in missed", RiskLevel.CAREGIVER, "provider_accepted", 1, now, now, "SM123")
        self.store.save_delivery(delivery)
        self.assertTrue(self.store.update_delivery_status("SM123", "delivered"))
        self.assertEqual(self.store.deliveries()[0].status, "delivered")

    def test_dotenv_loads_robot_settings_without_overriding_shell(self):
        env_file = Path(self.temp.name) / ".env"
        env_file.write_text("ROBOT_LLM_API_KEY='file-key'\nROBOT_LLM_MODEL=file-model\nIGNORED=value\n")
        with patch.dict("os.environ", {"ROBOT_LLM_MODEL": "shell-model"}, clear=True):
            load_dotenv(env_file)
            self.assertEqual(os.environ["ROBOT_LLM_API_KEY"], "file-key")
            self.assertEqual(os.environ["ROBOT_LLM_MODEL"], "shell-model")
            self.assertNotIn("IGNORED", os.environ)

    def test_offline_mode_disables_chat_and_transcription_api_clients(self):
        with patch.dict("os.environ", {"ROBOT_LLM_API_KEY": "saved-key", "ROBOT_OFFLINE_MODE": "true"}, clear=True):
            self.assertIsNone(OpenAICompatibleModel.from_environment())
            self.assertIsNone(OpenAITranscriber.from_environment())

    def test_offline_page_uses_browser_speech_recognition(self):
        with patch.dict("os.environ", {"ROBOT_OFFLINE_MODE": "true"}, clear=True):
            app = RobotApplication(Path(self.temp.name) / "offline-data")
            page = _page(app).decode()
        self.assertIn('data-server-transcription="false"', page)
        self.assertIn("window.SpeechRecognition||window.webkitSpeechRecognition", page)
        self.assertIn("No OpenAI transcription charges", page)

    def test_online_page_records_audio_for_server_transcription(self):
        with patch.dict("os.environ", {"ROBOT_LLM_API_KEY": "test-key"}, clear=True):
            app = RobotApplication(Path(self.temp.name) / "online-data")
            page = _page(app).decode()
        self.assertIn('data-server-transcription="true"', page)
        self.assertIn("new MediaRecorder", page)
        self.assertIn("'/api/voice'", page)
        self.assertIn("getUserMedia({audio:true})", page)

    def test_local_ai_uses_ollama_without_remote_transcription(self):
        with patch.dict("os.environ", {"ROBOT_LOCAL_AI": "true"}, clear=True):
            model = OpenAICompatibleModel.from_environment()
            self.assertIsNotNone(model)
            self.assertEqual(model.model, "llama3.2:3b")
            self.assertEqual(model.endpoint, "http://127.0.0.1:11434/v1/chat/completions")
            self.assertIsNone(OpenAITranscriber.from_environment())

    def test_media_round_trip(self):
        media = FamiliarMedia("family", "Family picnic", "https://example.test/pic.jpg", description="Family at the park")
        self.store.add_media(media)
        self.assertEqual(self.store.list_media(), [media])

    def test_care_profile_round_trip_and_personalizes_item_help(self):
        profile = CareProfile(
            preferred_name="Jo",
            important_people="Daughter Maya",
            usual_item_locations="Keys are usually in the blue bowl by the front door",
        )
        self.store.save_care_profile(profile)
        self.assertEqual(self.store.care_profile(), profile)
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("Where are my keys?", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertIn("Jo", reply)
        self.assertIn("blue bowl", reply)

    def test_normal_conversation_does_not_alert(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("I used to grow roses", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertTrue(reply)
        self.assertEqual(self.notifier.assessments, [])

    def test_configured_model_error_is_not_replaced_with_offline_reply(self):
        class BrokenModel:
            def reply(self, history, profile=None):
                raise RemoteServiceError("The API key was rejected.")

        service = ConversationService(self.store, BrokenModel(), self.notifier)
        with self.assertRaisesRegex(RemoteServiceError, "key was rejected"):
            service.respond("Hello", datetime.now(UTC))
        self.assertEqual([turn.role for turn in self.store.conversation()], ["user"])

    def test_offline_companion_gives_practical_help_finding_keys(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("I need help finding my keys", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertIn("by the door", reply)
        self.assertIn("one place at a time", reply)
        self.assertEqual(self.notifier.assessments, [])

    def test_help_me_find_keys_is_not_treated_as_an_emergency(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("Help me find my keys", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertIn("usual basket or bowl", reply)
        self.assertEqual(self.notifier.assessments, [])

    def test_offline_companion_does_not_give_medication_doses(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("Which pills should I take?", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.ROUTINE)
        self.assertIn("cannot tell you what dose", reply)

    def test_remote_companion_is_prompted_to_give_concrete_help_without_guessing(self):
        prompt = OpenAICompatibleModel.SYSTEM_PROMPT
        self.assertIn("concrete, low-risk next steps", prompt)
        self.assertIn("Never pretend to know", prompt)

    def test_conversation_safety_bypasses_model_and_alerts(self):
        service = ConversationService(self.store, OfflineCompanion(), self.notifier)
        reply, risk = service.respond("Help me, I fell", datetime.now(UTC))
        self.assertEqual(risk, RiskLevel.URGENT)
        self.assertIn("urgent help", reply)
        self.assertEqual(len(self.notifier.assessments), 1)

    def test_clear_conversation(self):
        ConversationService(self.store, OfflineCompanion(), self.notifier).respond("Hello", datetime.now(UTC))
        self.assertEqual(len(self.store.conversation()), 2)
        self.store.clear_conversation()
        self.assertEqual(self.store.conversation(), [])

    def test_transcriber_sends_multipart_audio(self):
        class Response(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()

        captured = {}

        def fake_open(request, timeout):
            captured["request"], captured["timeout"] = request, timeout
            return Response(b'{"text":"Hello FRED"}')

        with patch("dementia_care_robot.speech.urlopen", fake_open):
            result = OpenAITranscriber("secret", model="whisper-1").transcribe(b"audio-data", "audio/webm")
        request = captured["request"]
        self.assertEqual(result, "Hello FRED")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertIn(b'name="model"', request.data)
        self.assertIn(b"whisper-1", request.data)
        self.assertIn(b"audio-data", request.data)

    def test_transcriber_rejects_empty_audio(self):
        with self.assertRaisesRegex(ValueError, "No audio"):
            OpenAITranscriber("secret").transcribe(b"")

    def test_transcriber_explains_rejected_api_key(self):
        error = HTTPError("https://api.openai.com", 401, "Unauthorized", {}, BytesIO(b'{}'))
        with patch("dementia_care_robot.speech.urlopen", side_effect=error):
            with self.assertRaisesRegex(RemoteServiceError, "API key was rejected"):
                OpenAITranscriber("bad-key").transcribe(b"audio", "audio/webm")

    def test_local_ai_timeout_explains_how_to_start_ollama(self):
        from dementia_care_robot.api_errors import explain_api_error

        error = explain_api_error(TimeoutError(), "Local AI")
        self.assertIn("Ollama", str(error))
        self.assertIn("two minutes", str(error))

    def test_pico_bridge_sends_led_state_and_parses_switches(self):
        events = []
        stream = BytesIO()
        bridge = PicoBridge("unused", lambda switch, action: events.append((switch, action)), stream)
        bridge.set_led("listening")
        bridge.handle_line("SWITCH HELP PRESS\r\n")
        bridge.handle_line("unexpected input\n")
        self.assertEqual(stream.getvalue(), b"LED listening\n")
        self.assertEqual(events, [("help", "press")])

    def test_pico_bridge_rejects_unknown_led_state(self):
        bridge = PicoBridge("unused", lambda *_: None, BytesIO())
        with self.assertRaisesRegex(ValueError, "Unknown LED state"):
            bridge.set_led("rainbow")

    def test_missing_pico_reconnects_without_blocking_application_start(self):
        bridge = PicoBridge(str(Path(self.temp.name) / "missing-pico"), lambda *_: None)
        bridge.start()
        try:
            self.assertFalse(bridge.connected)
        finally:
            bridge.close()


if __name__ == "__main__": unittest.main()
