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
    def test_caregiver_music_upload_appears_in_activities(self):
        class Socket:
            def __init__(self, request):
                self.input, self.output = BytesIO(request), b''
            def makefile(self, *args): return self.input
            def sendall(self, data): self.output += data

        boundary = 'music-test-boundary'
        body = b''.join([
            b'--music-test-boundary\r\nContent-Disposition: form-data; name="title"\r\n\r\nA favorite song\r\n',
            b'--music-test-boundary\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nmusic\r\n',
            b'--music-test-boundary\r\nContent-Disposition: form-data; name="file"; filename="song.mp3"\r\nContent-Type: audio/mpeg\r\n\r\nID3test\r\n',
            b'--music-test-boundary--\r\n',
        ])
        with tempfile.TemporaryDirectory() as directory:
            app = RobotApplication(Path(directory))
            handler = make_handler(app)
            request = Socket(f'POST /upload HTTP/1.1\r\nHost: localhost\r\nContent-Type: multipart/form-data; boundary={boundary}\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body)
            handler(request, ('127.0.0.1', 1234), None)
            self.assertIn(b'303 See Other', request.output)
            self.assertEqual([(m.title, m.kind) for m in app.store.list_media()], [('A favorite song', 'music')])
            activities = Request('/activities')
            handler(activities, ('127.0.0.1', 1234), None)
            self.assertIn(b'A favorite song', activities.output)
            self.assertIn(b'Favorite music', activities.output)
            self.assertIn(b'data-src="/local-media/', activities.output)

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
                    ('/test', b'FRED laptop lab'),
                    ('/static/site/laptop-test.js', b'detectForVideo'),
                    ('/static/site/wake-voice.js', b'fredWakeCommand'),
                    ('/static/site/hri-gaze.js', b'WebSocket'),
                    ('/activities', b'Play, discover, and remember'),
                    ('/activities/', b'Finish a phrase'),
                    ('/static/site/activities.js', b'pairRound'),
                ]:
                    with self.subTest(path=path):
                        request = Request(path)
                        handler(request, ('127.0.0.1', 1234), None)
                        self.assertIn(b'200 OK', request.output)
                        self.assertIn(expected, request.output)
                        if path == '/activities':
                            self.assertIn(b'data-activity="puzzle"', request.output)
                            self.assertIn(b'data-activity="color"', request.output)
                            self.assertIn(b'data-activity="sort"', request.output)
                for path in ['/static/site/../../web.py', '/static/site/%2e%2e/.env', '/static/site/missing.css']:
                    request = Request(path)
                    handler(request, ('127.0.0.1', 1234), None)
                    self.assertIn(b'404 Not Found', request.output)
