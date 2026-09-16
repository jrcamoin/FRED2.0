import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dementia_care_robot.adapters import PiSpeaker
from dementia_care_robot.web import RobotApplication


class PiSpeechTests(unittest.TestCase):
    @patch("dementia_care_robot.adapters.shutil.which", return_value="/usr/bin/espeak-ng")
    @patch("dementia_care_robot.adapters.subprocess.run")
    def test_safe_text_input_and_selected_audio_device(self, run, which):
        run.return_value.stdout = b"wave audio"
        PiSpeaker("plughw:CARD=Headphones,DEV=0").say("--help; $(unsafe)")
        synthesis, playback = run.call_args_list
        self.assertEqual(synthesis.kwargs["input"], b"--help; $(unsafe)")
        self.assertEqual(playback.kwargs["input"], b"wave audio")
        self.assertEqual(playback.args[0], ["aplay", "-q", "-D", "plughw:CARD=Headphones,DEV=0"])
        self.assertNotIn("shell", synthesis.kwargs)

    @patch("dementia_care_robot.adapters.shutil.which", return_value=None)
    def test_missing_dependencies(self, which):
        with self.assertRaisesRegex(ValueError, "espeak-ng and alsa-utils"):
            PiSpeaker()

    def test_output_selection_and_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"ROBOT_OFFLINE_MODE": "1", "ROBOT_PI_SPEECH": "false"}):
            app = RobotApplication(Path(directory))
            self.assertEqual(app.speak_reply("Hello"), {"speech_output": "browser"})
            app.pi_speaker = Mock()
            self.assertEqual(app.speak_reply("Hello"), {"speech_output": "pi"})
            app.pi_speaker.say.assert_called_once_with("Hello")
            app.pi_speaker.say.side_effect = subprocess.TimeoutExpired("aplay", 120)
            result = app.speak_reply("Still return the text")
            self.assertEqual(result["speech_output"], "pi")
            self.assertIn("playback failed", result["speech_error"])
