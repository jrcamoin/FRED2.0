"""HumanFrame integration contracts (run with PYTHONPATH=src)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from dementia_care_robot.humanframe_integration import HumanFrameIntegration
from dementia_care_robot.web import RobotApplication, _page, make_handler


class HumanFrameConversionTests(unittest.TestCase):
    def test_record_wav_uses_sdk_and_cleans_up_audio(self):
        with tempfile.TemporaryDirectory() as td:
            audio_dir = Path(td)
            wav = audio_dir / 'sample.wav'
            wav.write_bytes(b'RIFF' + b'\0' * 40)
            sdk = Mock()
            sdk.audio.record.return_value = {'success': True, 'path': str(wav)}
            bridge = HumanFrameIntegration(sdk)
            with patch.object(HumanFrameIntegration, 'AUDIO_DIR', audio_dir):
                result = bridge.record_wav(3)
            self.assertEqual(result[:4], b'RIFF')
            self.assertFalse(wav.exists(), 'Raw voice should be removed after reading')
            sdk.audio.record.assert_called_once_with(duration=3)

    def test_rejects_untrusted_paths(self):
        with tempfile.TemporaryDirectory() as td:
            unexpected = Path(td) / 'other.wav'
            unexpected.write_bytes(b'RIFF')
            sdk = Mock()
            sdk.audio.record.return_value = {'success': True, 'path': str(unexpected)}
            bridge = HumanFrameIntegration(sdk)
            with self.assertRaises(RuntimeError):
                bridge.record_wav()
            self.assertTrue(unexpected.exists())

    def test_duration_is_bounded(self):
        bridge = HumanFrameIntegration(Mock())
        for duration in (0, 11, -1):
            with self.assertRaises(ValueError):
                bridge.record_wav(duration)

    def test_humanframe_resident_mic_button_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {'ROBOT_HUMANFRAME_MODE':'1', 'ROBOT_OFFLINE_MODE':'1'}, clear=True), patch('dementia_care_robot.web.HumanFrameIntegration', return_value=Mock()):
                app = RobotApplication(Path(td))
                page = _page(app).decode()
                self.assertNotIn('id="robotMicButton"', page, 'No transcription credentials means no robot microphone button')
                self.assertIn('humanframe-voice.js', page)
