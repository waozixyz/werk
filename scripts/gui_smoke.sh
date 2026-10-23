#!/bin/sh
# Renders Werkzeug's home screen in light and dark on private Xvfb displays,
# with disposable profiles, never the user's saved data.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
work="$root/build/gui-smoke"
rm -rf "$work"
mkdir -p "$work/home/.local/lib/werk/apps"
for app in pass auth calculator clock; do
    printf 'obsolete bundle\n' > "$work/home/.local/lib/werk/apps/$app.zx"
done
for mode in light dark; do
    mkdir -p "$work/$mode/data/profile" "$work/$mode/cache"
    value=1
    if [ "$mode" = dark ]; then
        value=2
    fi
    printf 'theme_mode=%s\n' "$value" > "$work/$mode/data/profile/settings.txt"
    python3 scripts/private-display.py \
        env -u WERK_ASSETS HOME="$work/home" WERK_DATA="$work/$mode/data" XDG_CACHE_HOME="$work/$mode/cache" \
        KRYON_CAPTURE_PATH="$work/werk-$mode.png" "$root/build/werk"
    test -s "$work/werk-$mode.png"
done
python3 - "$work" <<'PY'
from pathlib import Path
from PIL import Image
import sys
work = Path(sys.argv[1])
# Isolate the dark labels from the muted tile fills before text recognition.
with Image.open(work / "werk-light.png") as source:
    labels = source.convert("L").point(lambda value: 0 if value < 130 else 255)
    labels.resize((source.width * 3, source.height * 3)).save(work / "labels.png")
PY
rendered=$(tesseract "$work/labels.png" stdout --psm 11 2>/dev/null)
for app in Pass Auth Calculator Clock; do
    printf '%s\n' "$rendered" | grep -q "$app" || { echo "Missing preinstalled app: $app" >&2; exit 1; }
done
if cmp -s "$work/werk-light.png" "$work/werk-dark.png"; then
    echo 'Werkzeug light and dark themes rendered the same frame' >&2
    exit 1
fi
echo 'Werkzeug desktop: light and dark home screens rendered on private Xvfb displays'
