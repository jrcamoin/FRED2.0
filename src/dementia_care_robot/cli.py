import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .adapters import ConsoleCaregiverNotifier, ConsoleSpeaker
from .config import load_dotenv
from .coordinator import CareCoordinator
from .models import CheckIn, Reminder


def run_demo() -> None:
    coordinator = CareCoordinator(ConsoleSpeaker(), ConsoleCaregiverNotifier())
    coordinator.deliver_reminder(Reminder("demo-water", "Please have a glass of water.", datetime.now(UTC)))
    response = input("YOUR RESPONSE: ")
    coordinator.handle_check_in(CheckIn(response, datetime.now(UTC)))


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Dementia care robot prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="run a console interaction")
    check = commands.add_parser("hardware-check", help="check Raspberry Pi display, audio, power, and Pico access")
    check.add_argument("--pico", default="auto", help="Pico device path or auto")
    export = commands.add_parser("export-feedback", help="export caregiver-reviewed examples as private JSONL")
    export.add_argument("--data-dir", default="data")
    export.add_argument("--output", required=True)
    web = commands.add_parser("web", help="run the local caregiver and patient dashboard")
    web.add_argument("--data-dir", default="data")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    web.add_argument("--open", action="store_true", dest="open_browser")
    web.add_argument("--certfile", help="TLS certificate required for microphone access from another device")
    web.add_argument("--keyfile", help="TLS private key")
    web.add_argument("--pico", help="Pico USB serial device, or auto to discover it")
    mode = web.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="disable model API calls and use the built-in testing companion")
    mode.add_argument("--local-ai", action="store_true", help="generate replies locally with Ollama (default model: llama3.2:3b)")
    args = parser.parse_args()
    if args.command == "demo":
        run_demo()
    elif args.command == "hardware-check":
        from .hardware import hardware_report
        failed=False
        for name,ok,detail in hardware_report(args.pico):
            print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
            failed = failed or not ok
        raise SystemExit(1 if failed else 0)
    elif args.command == "export-feedback":
        from .storage import SQLiteStore
        rows=SQLiteStore(Path(args.data_dir)/"robot.db").feedback()
        output=Path(args.output)
        output.write_text("".join(json.dumps({"prompt":x.prompt,"response":x.response,"rating":x.rating,"correction":x.correction},ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
        output.chmod(0o600)
        print(f"Exported {len(rows)} reviewed response(s) to {output}. Treat this file as sensitive personal data.")
    elif args.command == "web":
        if args.offline:
            os.environ["ROBOT_OFFLINE_MODE"] = "1"
        elif args.local_ai:
            os.environ["ROBOT_OFFLINE_MODE"] = "0"
            os.environ["ROBOT_LOCAL_AI"] = "1"
        from .web import serve
        if bool(args.certfile) != bool(args.keyfile):
            parser.error("--certfile and --keyfile must be supplied together")
        serve(args.data_dir, args.host, args.port, args.open_browser, args.certfile, args.keyfile, args.pico)


if __name__ == "__main__":
    main()
