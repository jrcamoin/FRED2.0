import argparse
from datetime import UTC, datetime

from .adapters import ConsoleCaregiverNotifier, ConsoleSpeaker
from .coordinator import CareCoordinator
from .models import CheckIn, Reminder


def run_demo() -> None:
    coordinator = CareCoordinator(ConsoleSpeaker(), ConsoleCaregiverNotifier())
    coordinator.deliver_reminder(Reminder("demo-water", "Please have a glass of water.", datetime.now(UTC)))
    response = input("YOUR RESPONSE: ")
    coordinator.handle_check_in(CheckIn(response, datetime.now(UTC)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Dementia care robot prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="run a console interaction")
    web = commands.add_parser("web", help="run the local caregiver and patient dashboard")
    web.add_argument("--data-dir", default="data")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    web.add_argument("--open", action="store_true", dest="open_browser")
    web.add_argument("--certfile", help="TLS certificate required for microphone access from another device")
    web.add_argument("--keyfile", help="TLS private key")
    web.add_argument("--pico", help="Pico USB serial device, for example /dev/ttyACM0")
    args = parser.parse_args()
    if args.command == "demo":
        run_demo()
    elif args.command == "web":
        from .web import serve
        if bool(args.certfile) != bool(args.keyfile):
            parser.error("--certfile and --keyfile must be supplied together")
        serve(args.data_dir, args.host, args.port, args.open_browser, args.certfile, args.keyfile, args.pico)


if __name__ == "__main__":
    main()
