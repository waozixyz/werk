#!/bin/sh
# Pass's saved settings, profiles and theme reach Werkzeug on its first
# start; a disposable fixture folder stands in for the old working folder.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work="$root/build/migration-test"
rm -rf "$work"
mkdir -p "$work/legacy" "$work/data" "$work/cache"
cd "$work/legacy"
printf '24' > .kryon_pass_length.txt
printf '2' > .kryon_pass_theme_mode.txt
printf '5' > .kryon_pass_theme_id.txt
printf 'Example\texample.com\talice\t24\t1\t1\t1\t1\t1\t\n' > profiles.tsv
env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS xvfb-run -a -e /dev/stderr \
    env WERKZEUG_DATA="$work/data" XDG_CACHE_HOME="$work/cache" WERKZEUG_ASSETS="$root/build" \
    KRYON_CAPTURE_PATH="$work/home.png" "$root/build/werkzeug"
test "$(cat "$work/data/apps/pass/.kryon_pass_length.txt")" = 24
cmp "$work/legacy/profiles.tsv" "$work/data/apps/pass/profiles.tsv"
grep -qx 'theme_mode=2' "$work/data/profile/settings.txt"
grep -qx 'accent=5' "$work/data/profile/settings.txt"
test "$(stat -c %a "$work/data/apps/pass/profiles.tsv")" = 600
# A second start leaves the migrated folder alone.
printf '30' > .kryon_pass_length.txt
env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS xvfb-run -a -e /dev/stderr \
    env WERKZEUG_DATA="$work/data" XDG_CACHE_HOME="$work/cache" WERKZEUG_ASSETS="$root/build" \
    KRYON_CAPTURE_PATH="$work/home.png" "$root/build/werkzeug"
test "$(cat "$work/data/apps/pass/.kryon_pass_length.txt")" = 24
echo 'Pass data migration: settings, profiles and theme moved once'
