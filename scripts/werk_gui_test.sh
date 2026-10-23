#!/bin/sh
# Runs the Werkzeug GUI test on its own private Xvfb display, never the
# developer's desktop.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
exec python3 scripts/private-display.py python3 scripts/werk_gui_test.py
