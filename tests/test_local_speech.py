import base64
import json
import os
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from dementia_care_robot.speech import LocalTranscriber, SpeechNotConfigured, configured_transcriber
from dementia_care_robot.web import RobotApplication, make_handler


class LocalSpeechTests(unittest.TestCase):
    def transcriber(self, directory):
        module = Mock()
        rec = module.KaldiRecognizer.return_value
        rec.AcceptWaveform.side_effect = [True, False]
        rec.Result.return_value = '{"text":"hello"}'
        rec.FinalResult.return_value = '{"text":"fred"}'
        with patch.dict("sys.modules", {"vosk": module}), patch("dementia_care_robot.speech.shutil.which", return_value="/usr/bin/ffmpeg"):
            return LocalTranscriber(directory), rec

    def test_decode_and_join_results(self):
        with tempfile.TemporaryDirectory() as directory:
            transcriber, rec = self.transcriber(directory)
            with patch("dementia_care_robot.speech.subprocess.run", return_value=Mock(stdout=b'\0' * 16000)) as run:
                self.assertEqual(transcriber.transcribe(b"webm"), "hello fred")
                self.assertEqual(run.call_args.kwargs["input"], b"webm")
                self.assertIn("16000", run.call_args.args[0])
                self.assertEqual(rec.AcceptWaveform.call_count, 2)

    def test_silence_empty_and_decode_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            transcriber, rec = self.transcriber(directory)
            with self.assertRaisesRegex(ValueError, "No audio"):
                transcriber.transcribe(b"")
            rec.FinalResult.return_value = '{"text":""}'
            with patch("dementia_care_robot.speech.subprocess.run", return_value=Mock(stdout=b"")):
                with self.assertRaisesRegex(ValueError, "No speech"):
                    transcriber.transcribe(b"clip")
            with patch("dementia_care_robot.speech.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 45)):
                with self.assertRaisesRegex(ValueError, "decode"):
                    transcriber.transcribe(b"clip")

    def test_missing_model(self):
        with self.assertRaisesRegex(SpeechNotConfigured, "extracted Vosk"):
            LocalTranscriber("/nonexistent/fred-model")

    def test_local_selected_even_offline_without_remote_fallback(self):
        with patch.dict(os.environ, {"ROBOT_OFFLINE_MODE":"1", "ROBOT_VOSK_MODEL":"/model"}), patch("dementia_care_robot.speech.LocalTranscriber") as local, patch("dementia_care_robot.speech.OpenAITranscriber.from_environment") as remote:
            self.assertIs(configured_transcriber(), local.return_value)
            remote.assert_not_called()

    def test_voice_http_request_transcribes_and_speaks_locally(self):
        class Socket:
            def __init__(self):
                body = json.dumps({"audio":base64.b64encode(b"clip").decode(),"content_type":"audio/webm"}).encode()
                self.input = BytesIO(b"POST /api/voice HTTP/1.1\r\nHost: localhost\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
                self.output = b""
            def makefile(self, *args): return self.input
            def sendall(self, data): self.output += data
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"ROBOT_OFFLINE_MODE":"1", "ROBOT_PI_SPEECH":"false"}), patch("dementia_care_robot.web.configured_transcriber") as configured:
            configured.return_value.transcribe.return_value = "hello"
            app = RobotApplication(Path(directory))
            app.pi_speaker = Mock()
            sock = Socket()
            make_handler(app)(sock, ("127.0.0.1",1234), None)
            self.assertIn(b"200 OK", sock.output)
            result = json.loads(sock.output.split(b"\r\n\r\n",1)[1])
            self.assertEqual(result["transcript"], "hello")
            self.assertEqual(result["speech_output"], "pi")
            app.pi_speaker.say.assert_called_once_with(result["reply"])
            configured.return_value.transcribe.assert_called_once_with(b"clip","audio/webm")
