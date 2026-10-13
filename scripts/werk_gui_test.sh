#!/bin/sh
# Runs the Werk GUI test on its own private Xvfb display, never the
# developer's desktop.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
exec env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS xvfb-run -a -e /dev/stderr \
    env WERK_TEST_PRIVATE_DISPLAY=1 python3 scripts/werk_gui_test.py
