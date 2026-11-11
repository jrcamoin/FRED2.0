import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from dementia_care_robot.web import RobotApplication, make_handler
from dementia_care_robot.models import CareProfile, ConversationTurn
from datetime import UTC, datetime


class MessageTests(unittest.TestCase):
    def test_pi_caregiver_setup_requires_session_and_cannot_reset_password(self):
        class Socket:
            def __init__(self, request):
                self.input, self.output = BytesIO(request), b''
            def makefile(self, *args): return self.input
            def sendall(self, data): self.output += data

        def request(handler, method, path, fields=None, cookie=None, origin=None):
            body = urlencode(fields or {}).encode()
            headers = f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(body)}\r\n'
            if cookie: headers += f'Cookie: {cookie}\r\n'
            if origin: headers += f'Origin: {origin}\r\n'
            sock = Socket(headers.encode() + b'\r\n' + body)
            handler(sock, ('127.0.0.1', 1234), None)
            return sock.output

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'ROBOT_CAREGIVER_AUTH_ENABLED': '1'}):
            app = RobotApplication(Path(directory))
            handler = make_handler(app)
            self.assertIn(b'Set up FRED', request(handler, 'GET', '/caregiver'))
            created = request(handler, 'POST', '/onboarding', {'step': 1, 'password': 'strong-password', 'confirm': 'strong-password'})
            self.assertIn(b'200 OK', created)
            cookie = created.split(b'Set-Cookie: ', 1)[1].split(b';', 1)[0].decode()
            self.assertIn(b'HTTP/1.0 403 ', request(handler, 'POST', '/onboarding', {'step': 1, 'password': 'other-password', 'confirm': 'other-password'}))
            self.assertIn(b'HTTP/1.0 403 ', request(handler, 'POST', '/onboarding', {'step': 2, 'quiet_start': '21:00', 'quiet_end': '07:00'}))
            self.assertIn(b'200 OK', request(handler, 'POST', '/onboarding', {'step': 2, 'quiet_start': '21:00', 'quiet_end': '07:00'}, cookie))
            self.assertIn(b'Caregiver sign in', request(handler, 'GET', '/caregiver'))
            self.assertIn(b'Add reminder', request(handler, 'GET', '/caregiver', cookie=cookie))
            self.assertIn(b'401 Unauthorized', request(handler, 'POST', '/reminders', {'message': 'Drink water'}))
            self.assertIn(b'HTTP/1.0 403 ', request(handler, 'POST', '/reminders', {'message': 'Drink water'}, cookie, 'https://untrusted.example'))

    def test_resident_can_clear_conversation(self):
        class Socket:
            def __init__(self, request):
                self.input = BytesIO(request)
                self.output = b''

            def makefile(self, *args):
                return self.input

            def sendall(self, data):
                self.output += data

        with tempfile.TemporaryDirectory() as directory:
            app = RobotApplication(Path(directory))
            app.store.append_turn(ConversationTurn('user', 'Private question', datetime.now(UTC)))
            handler = make_handler(app)

            website = Socket(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            handler(website, ('127.0.0.1', 1234), None)
            self.assertIn(b'Human Frame Robotics', website.output)
            self.assertIn(b'href="/app"', website.output)
            self.assertNotIn(b'Private question', website.output)

            page = Socket(b'GET /app HTTP/1.1\r\nHost: localhost\r\n\r\n')
            handler(page, ('127.0.0.1', 1234), None)
            self.assertIn(b'Clear conversation', page.output)
            self.assertIn(b'Private question', page.output)

            clear = Socket(b'POST /conversation/clear HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n')
            handler(clear, ('127.0.0.1', 1234), None)

            self.assertIn(b'303 See Other', clear.output)
            self.assertIn(b'Location: /app?', clear.output)
            self.assertEqual(app.store.conversation(), [])

    def test_caregiver_dashboard_is_available_without_login(self):
        class Socket:
            def __init__(self):
                self.input = BytesIO(b'GET /caregiver HTTP/1.1\r\nHost: localhost\r\n\r\n')
                self.output = b''

            def makefile(self, *args):
                return self.input

            def sendall(self, data):
                self.output += data

        with tempfile.TemporaryDirectory() as directory:
            handler = make_handler(RobotApplication(Path(directory)))
            sock = Socket()
            handler(sock, ('127.0.0.1', 1234), None)

        self.assertIn(b'200 OK', sock.output)
        self.assertIn(b'Add reminder', sock.output)
        self.assertIn(b'Upload family media', sock.output)
        self.assertNotIn(b'Caregiver sign in', sock.output)

    def test_head_display_and_shared_state_endpoints(self):
        class Socket:
            def __init__(self, request):
                self.input, self.output = BytesIO(request), b''
            def makefile(self, *args): return self.input
            def sendall(self, data): self.output += data

        with tempfile.TemporaryDirectory() as directory:
            app = RobotApplication(Path(directory)); handler = make_handler(app)
            head = Socket(b'GET /head HTTP/1.1\r\nHost: localhost\r\n\r\n')
            handler(head, ('127.0.0.1', 1234), None)
            self.assertIn(b'FRED head', head.output)
            self.assertIn(b'head-tracking.js', head.output)
            self.assertIn(b'Show tracking', head.output)
            state = Socket(b'GET /api/robot-state HTTP/1.1\r\nHost: localhost\r\n\r\n')
            handler(state, ('127.0.0.1', 1234), None)
            payload = json.loads(state.output.split(b'\r\n\r\n', 1)[1])
            self.assertEqual(payload['state'], 'idle')
            head_handler = make_handler(app, head_only=True)
            head_root = Socket(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
            head_handler(head_root, ('127.0.0.1', 1234), None)
            self.assertIn(b'Start Hey FRED', head_root.output)
            self.assertIn(b'Tap to speak', head_root.output)
            self.assertNotIn(b'happyDemo', head_root.output)
            self.assertNotIn(b'sadDemo', head_root.output)
            self.assertIn(b'wake-voice.js', head_root.output)
            audio = json.dumps({'audio': 'dGVzdA==', 'content_type': 'audio/webm'}).encode()
            voice = Socket(b'POST /api/voice HTTP/1.1\r\nHost: localhost\r\nContent-Length: ' + str(len(audio)).encode() + b'\r\n\r\n' + audio)
            with patch.object(app, 'voice_turn', return_value=('Hello FRED', 'Hello there', 'none')) as turn:
                head_handler(voice, ('127.0.0.1', 1234), None)
            self.assertIn(b'200 OK', voice.output)
            self.assertEqual(json.loads(voice.output.split(b'\r\n\r\n', 1)[1])['transcript'], 'Hello FRED')
            turn.assert_called_once_with(b'test', 'audio/webm')
            tracker = Socket(b'GET /static/site/head-tracking.js HTTP/1.1\r\nHost: localhost\r\n\r\n')
            head_handler(tracker, ('127.0.0.1', 1234), None)
            self.assertIn(b'FaceDetector', tracker.output)
            emotions = Socket(b'GET /static/site/head-emotions.js HTTP/1.1\r\nHost: localhost\r\n\r\n')
            head_handler(emotions, ('127.0.0.1', 1234), None)
            self.assertIn(b'200 OK', emotions.output)
            self.assertIn(b'AudioContext', emotions.output)
            blocked = Socket(b'GET /caregiver HTTP/1.1\r\nHost: localhost\r\n\r\n')
            head_handler(blocked, ('127.0.0.1', 1234), None)
            self.assertIn(b'404 Not Found', blocked.output)

    def test_offline_json_conversation_and_invalid_input(self):
        class Socket:
            def __init__(self, payload):
                body = json.dumps(payload).encode()
                self.input = BytesIO(b'POST /api/conversation HTTP/1.1\r\nHost: localhost\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
                self.output = b''

            def makefile(self, *args):
                return self.input

            def sendall(self, data):
                self.output += data

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'ROBOT_OFFLINE_MODE': '1'}):
            app = RobotApplication(Path(directory))
            app.store.save_care_profile(CareProfile(daily_routine='Breakfast at eight', usual_item_locations='Keys: blue bowl; Phone: bedside table'))
            handler = make_handler(app)
            for message, expected in [('What is my routine?', 'Breakfast at eight'), ('Where is my phone?', 'bedside table')]:
                sock = Socket({'message': message})
                handler(sock, ('127.0.0.1', 1234), None)
                self.assertIn(b'200 OK', sock.output)
                reply = json.loads(sock.output.split(b'\r\n\r\n', 1)[1])['reply']
                self.assertIn(expected, reply)
                if 'phone' in message:
                    self.assertNotIn('blue bowl', reply)
            count = len(app.store.conversation())
            for payload in [[], {'message': ''}, {'message': 1}, {'message': 'x' * 2001}]:
                sock = Socket(payload)
                handler(sock, ('127.0.0.1', 1234), None)
                self.assertIn(b'400 Bad Request', sock.output)
            self.assertEqual(len(app.store.conversation()), count)
