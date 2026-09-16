import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class DeviceSecrets:
    """Device-local authenticated encryption and signed caregiver sessions."""

    def __init__(self, data_dir: Path) -> None:
        self.key_path = data_dir / ".device-key"
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            self.key_path.chmod(0o600)
        key = self.key_path.read_bytes().strip()
        self.fernet = Fernet(key)
        self.signing_key = hashlib.sha256(key + b"session").digest()

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return "enc:" + self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if not value or not value.startswith("enc:"):
            return value
        try:
            return self.fernet.decrypt(value[4:].encode()).decode()
        except InvalidToken as error:
            raise ValueError("Encrypted data cannot be opened with this device key") from error

    def encrypt_bytes(self, value: bytes) -> bytes:
        return self.fernet.encrypt(value)

    def decrypt_bytes(self, value: bytes) -> bytes:
        return self.fernet.decrypt(value)

    @staticmethod
    def hash_password(password: str, salt: bytes | None = None) -> str:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return f"pbkdf2_sha256$310000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            _, rounds, salt, expected = encoded.split("$", 3)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds))
            return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
        except (ValueError, TypeError):
            return False

    def issue_session(self, ttl_seconds: int = 43_200) -> str:
        payload = base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + ttl_seconds, "nonce": secrets.token_hex(8)}).encode()).decode()
        signature = hmac.new(self.signing_key, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def valid_session(self, token: str) -> bool:
        try:
            payload, signature = token.split(".", 1)
            valid = hmac.compare_digest(signature, hmac.new(self.signing_key, payload.encode(), hashlib.sha256).hexdigest())
            data = json.loads(base64.urlsafe_b64decode(payload))
            return valid and int(data["exp"]) >= int(time.time())
        except (ValueError, KeyError, json.JSONDecodeError):
            return False
