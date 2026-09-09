import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Load ROBOT_* settings from a local file without overriding the shell."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key.startswith("ROBOT_"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def offline_mode() -> bool:
    return os.environ.get("ROBOT_OFFLINE_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
