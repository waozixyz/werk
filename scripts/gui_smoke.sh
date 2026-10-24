#!/bin/sh
# Renders Werkzeug's home screen in light and dark, and its --mini tool tiles,
# on private Xvfb displays with disposable profiles, never the user's saved
# data.
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
python3 scripts/private-display.py \
    env -u WERK_ASSETS HOME="$work/home" WERK_DATA="$work/light/data" XDG_CACHE_HOME="$work/light/cache" \
    KRYON_CAPTURE_PATH="$work/werk-mini.png" "$root/build/werk" --mini
test -s "$work/werk-mini.png"
python3 - "$work" <<'PY'
from pathlib import Path
from PIL import Image
import sys
work = Path(sys.argv[1])
# Isolate the dark labels from the muted tile fills before text recognition.
for name in ("light", "mini"):
    with Image.open(work / f"werk-{name}.png") as source:
        labels = source.convert("L").point(lambda value: 0 if value < 130 else 255)
        labels.resize((source.width * 3, source.height * 3)).save(work / f"labels-{name}.png")
PY
rendered=$(tesseract "$work/labels-light.png" stdout --psm 11 2>/dev/null)
for app in Pass Auth Calculator Clock; do
    printf '%s\n' "$rendered" | grep -q "$app" || { echo "Missing preinstalled app: $app" >&2; exit 1; }
done
# Mini mode is the tool tiles alone, without Profile, search or title.
rendered=$(tesseract "$work/labels-mini.png" stdout --psm 11 2>/dev/null)
for app in Pass Auth Calculator Clock; do
    printf '%s\n' "$rendered" | grep -q "$app" || { echo "Missing mini tile: $app" >&2; exit 1; }
done
for hidden in Profile Find Werkzeug; do
    if printf '%s\n' "$rendered" | grep -qi "$hidden"; then
        echo "Werkzeug --mini shows $hidden" >&2
        exit 1
    fi
done
if cmp -s "$work/werk-light.png" "$work/werk-dark.png"; then
    echo 'Werkzeug light and dark themes rendered the same frame' >&2
    exit 1
fi
echo 'Werkzeug desktop: light and dark home screens and --mini tool tiles rendered on private Xvfb displays'
