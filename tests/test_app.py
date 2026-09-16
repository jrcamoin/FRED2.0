"""End-to-end tests for the development web baseline."""

import re
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select
from werkzeug.security import check_password_hash

from robot import Robot, RobotState
from system import create_app
from system.auth.models import User
from system.extensions import db


class HumanFrameAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temporary_directory.cleanup()

    def register(
        self,
        username: str = "ada",
        email: str = "ada@example.com",
        password: str = "correct-horse",
    ):
        return self.client.post(
            "/register",
            data={"username": username, "email": email, "password": password},
        )

    def login(self, identifier: str = "ada", password: str = "correct-horse"):
        return self.client.post(
            "/login", data={"identifier": identifier, "password": password}
        )

    def logout(self):
        return self.client.post("/logout")

    def test_homepage_loads_login_for_anonymous_user(self) -> None:
        response = self.client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"HumanFrame", response.data)
        self.assertIn(b"Welcome back", response.data)

    def test_auth_forms_have_csrf_protection(self) -> None:
        self.app.config["WTF_CSRF_ENABLED"] = True
        page = self.client.get("/register")
        match = re.search(b'name="csrf_token" value="([^"]+)"', page.data)
        self.assertIsNotNone(match)
        assert match is not None

        registration = self.client.post(
            "/register",
            data={
                "csrf_token": match.group(1).decode(),
                "username": "grace",
                "email": "grace@example.com",
                "password": "secure-password",
            },
        )
        self.assertEqual(registration.status_code, 302)
        self.assertEqual(self.client.post("/logout").status_code, 400)

    def test_registration_hashes_password_and_opens_dashboard(self) -> None:
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))

        with self.app.app_context():
            user = db.session.scalar(select(User).where(User.username == "ada"))
            self.assertIsNotNone(user)
            assert user is not None
            self.assertNotEqual(user.password_hash, "correct-horse")
            self.assertTrue(check_password_hash(user.password_hash, "correct-horse"))

        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Welcome, ada", dashboard.data)

    def test_duplicate_usernames_and_emails_are_rejected_case_insensitively(self) -> None:
        self.register()
        self.logout()

        duplicate_username = self.register("ADA", "different@example.com")
        self.assertEqual(duplicate_username.status_code, 400)
        self.assertIn(b"already registered", duplicate_username.data)

        duplicate_email = self.register("different", "ADA@EXAMPLE.COM")
        self.assertEqual(duplicate_email.status_code, 400)
        self.assertIn(b"already registered", duplicate_email.data)

    def test_login_accepts_username_or_email_and_rejects_invalid_password(self) -> None:
        self.register()
        self.logout()

        invalid = self.login(password="wrong-password")
        self.assertEqual(invalid.status_code, 401)
        self.assertIn(b"Invalid username/email or password", invalid.data)
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

        by_email = self.login(identifier="ADA@EXAMPLE.COM")
        self.assertEqual(by_email.status_code, 302)
        self.assertTrue(by_email.headers["Location"].endswith("/dashboard"))

    def test_protected_pages_redirect_anonymous_users(self) -> None:
        for path in ("/dashboard", "/robot"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_authenticated_home_dashboard_robot_and_logout(self) -> None:
        self.register()

        home = self.client.get("/")
        self.assertEqual(home.status_code, 302)
        self.assertTrue(home.headers["Location"].endswith("/dashboard"))

        robot_page = self.client.get("/robot")
        self.assertEqual(robot_page.status_code, 200)
        for expected in (
            b"Robot UI",
            b"IDLE",
            b"NEUTRAL",
            b"NOT CONNECTED / SIMULATED",
            b"SIMULATED",
        ):
            self.assertIn(expected, robot_page.data)

        logout = self.logout()
        self.assertEqual(logout.status_code, 302)
        self.assertTrue(logout.headers["Location"].endswith("/login"))
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_external_next_url_is_not_used_after_login(self) -> None:
        self.register()
        self.logout()
        response = self.client.post(
            "/login",
            data={
                "identifier": "ada",
                "password": "correct-horse",
                "next": "https://example.com/escape",
            },
        )
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))


class RobotDomainTests(unittest.TestCase):
    def test_robot_states_are_importable_and_complete(self) -> None:
        self.assertEqual(
            [state.value for state in RobotState],
            ["idle", "listening", "thinking", "speaking", "moving", "error"],
        )

    def test_robot_starts_idle_and_accepts_only_robot_states(self) -> None:
        robot = Robot()
        self.assertIs(robot.state, RobotState.IDLE)

        robot.set_state(RobotState.LISTENING)
        self.assertIs(robot.state, RobotState.LISTENING)

        with self.assertRaises(TypeError):
            robot.set_state("idle")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
