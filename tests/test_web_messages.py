import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from dementia_care_robot.web import RobotApplication, make_handler
from dementia_care_robot.models import CareProfile, ConversationTurn
from datetime import UTC, datetime


class MessageTests(unittest.TestCase):
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
