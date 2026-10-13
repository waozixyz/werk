#!/bin/sh
# Renders Werkzeug's home screen in light and dark on private Xvfb displays,
# with disposable profiles, never the user's saved data.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
work="$root/build/gui-smoke"
rm -rf "$work"
for mode in light dark; do
    mkdir -p "$work/$mode/data/profile" "$work/$mode/cache"
    value=1
    if [ "$mode" = dark ]; then
        value=2
    fi
    printf 'theme_mode=%s\n' "$value" > "$work/$mode/data/profile/settings.txt"
    env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS xvfb-run -a -e /dev/stderr \
        env WERK_DATA="$work/$mode/data" XDG_CACHE_HOME="$work/$mode/cache" WERK_ASSETS="$root/build" \
        KRYON_CAPTURE_PATH="$work/werk-$mode.png" "$root/build/werk"
    test -s "$work/werk-$mode.png"
done
if cmp -s "$work/werk-light.png" "$work/werk-dark.png"; then
    echo 'Werkzeug light and dark themes rendered the same frame' >&2
    exit 1
fi
echo 'Werkzeug desktop: light and dark home screens rendered on private Xvfb displays'
