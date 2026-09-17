"""Verify the public sites and packaged assets stay separate from private data."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dementia_care_robot.web import RobotApplication, make_handler


class Request:
    def __init__(self, path):
        self.input = BytesIO(f'GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode())
        self.output = b''

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output += data


class WebsiteTests(unittest.TestCase):
    def test_public_routes_assets_and_private_path_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            app = RobotApplication(Path(directory))
            handler = make_handler(app)
            with patch.object(app.store, 'conversation', side_effect=AssertionError('Public routes must not read conversations')):
                for path, expected in [
                    ('/', b'Technology,'),
                    ('/fred', b'A familiar presence.'),
                    ('/fred/', b'href="/caregiver"'),
                    ('/static/site/styles.css', b'text/css'),
                    ('/static/site/app.css', b'text/css'),
                    ('/static/site/fred.css', b'text/css'),
                    ('/static/site/conversion.css', b'text/css'),
                    ('/static/site/script.js', b'const header'),
                    ('/static/site/assets/hero-robot.png', b'image/png'),
                ]:
                    with self.subTest(path=path):
                        request = Request(path)
                        handler(request, ('127.0.0.1', 1234), None)
                        self.assertIn(b'200 OK', request.output)
                        self.assertIn(expected, request.output)
                for path in ['/static/site/../../web.py', '/static/site/%2e%2e/.env', '/static/site/missing.css']:
                    request = Request(path)
                    handler(request, ('127.0.0.1', 1234), None)
                    self.assertIn(b'404 Not Found', request.output)
