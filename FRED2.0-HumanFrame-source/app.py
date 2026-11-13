"""HumanFrame Runtime entrypoint for FRED 2.0.

The Runtime owns this process and its lifecycle. Do not start a second systemd
service or a second HTTP listener on the physical robot.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# The robot-side deployer installs requirements before installing the SDK. It
# does not install the application itself as an editable package, so load the
# packaged FRED source directly rather than relying on `pip install -e .`.
sys.path.insert(0, str(ROOT / "src"))

from dementia_care_robot.config import load_dotenv  # noqa: E402
from dementia_care_robot.web import serve  # noqa: E402


def main():
    manifest = json.loads((ROOT / "humanframe.json").read_text(encoding="utf-8"))
    os.umask(0o077)
    data_dir = Path(os.environ.get("FRED_DATA_DIR", "/opt/humanframe/data/fred-companion"))
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Device-specific secrets never belong in a ZIP. The data directory (and
    # fred.env if present) survives deployment of a new application version.
    load_dotenv(data_dir / "fred.env")
    os.environ["ROBOT_HUMANFRAME_MODE"] = "1"
    os.environ["ROBOT_CAREGIVER_AUTH_ENABLED"] = "1"

    # Raw Pico serial access is intentionally opt-in, not a HumanFrame SDK API.
    pico = os.environ.get("FRED_PICO_DEVICE") or os.environ.get("ROBOT_PICO_DEVICE") or None
    serve(
        data_dir=data_dir,
        host="127.0.0.1",
        port=int(manifest["port"]),
        head_port=None,
        open_browser=False,
        pico_device=pico,
    )


if __name__ == "__main__":
    main()
