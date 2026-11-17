#!/bin/sh
# Pass's settings, profiles and secure master against a mock Werkzeug host,
# natively and as a portable bundle.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
ziran_root=$("$ziran" pkg path ziran)
set -- --project --root . --module-path tests
mkdir -p build/pass-state-test
"$ziran" build "$@" --target=c -o build/pass-state-test/c tests/pass_state_test.zi
${CC:-cc} -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections -I"$ziran_root/include" -Ibuild/pass-state-test/c build/pass-state-test/c/*.c -o build/pass-state-test/native
env -u DISPLAY -u WAYLAND_DISPLAY build/pass-state-test/native
"$ziran" bundle "$@" --entry pass_state_test:PassStateAnswer --bind-host pass_state_host \
    -o build/pass-state-test/portable.zx tests/pass_state_test.zi
test "$("$ziran" run build/pass-state-test/portable.zx)" = 42
echo 'Pass state: native and portable tests pass'
