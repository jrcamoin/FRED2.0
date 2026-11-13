#!/bin/sh
# Run from the Pi desktop user's labwc autostart, not from the system service.
set -eu

CHROMIUM=${FRED_CHROMIUM:-chromium}
PROFILE_ROOT=${XDG_DATA_HOME:-"$HOME/.local/share"}/fred

command -v "$CHROMIUM" >/dev/null 2>&1 || { echo "Chromium is not installed" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is not installed" >&2; exit 1; }

# The display session can begin before systemd finishes starting FRED.
until curl --silent --fail --max-time 2 http://127.0.0.1:8080/app >/dev/null &&
      curl --silent --fail --max-time 2 http://127.0.0.1:8081/ >/dev/null; do
    sleep 2
done

mkdir -p "$PROFILE_ROOT/head" "$PROFILE_ROOT/body"

while :; do
    "$CHROMIUM" --user-data-dir="$PROFILE_ROOT/head" \
        --enable-speech-dispatcher --autoplay-policy=no-user-gesture-required \
        --no-first-run --noerrdialogs \
        --disable-session-crashed-bubble --app=http://127.0.0.1:8081/
    sleep 3
done &

while :; do
    "$CHROMIUM" --user-data-dir="$PROFILE_ROOT/body" \
        --enable-speech-dispatcher --no-first-run --noerrdialogs \
        --disable-session-crashed-bubble --app=http://127.0.0.1:8080/app
    sleep 3
done &

wait
