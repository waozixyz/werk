#!/bin/sh
# Pass's settings, profiles and secure master against a mock Werkzeug host,
# natively and as a portable bundle.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
ziran_root=$("$ziran" pkg path ziran)
kryon=$("$ziran" pkg path kryon)
args="--root tests --module-path apps/pass --module-path shared --module-path kryon=$kryon/src/backend --module-path kryon=$kryon/src/ui --module-path $kryon/src/ui --module-path $ziran_root/std"
mkdir -p build/pass-state-test
"$ziran" build $args --target=c -o build/pass-state-test/c tests/pass_state_test.zi
${CC:-cc} -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections -I"$ziran_root/include" -Ibuild/pass-state-test/c build/pass-state-test/c/*.c -o build/pass-state-test/native
env -u DISPLAY -u WAYLAND_DISPLAY build/pass-state-test/native
binds=""
for name in ReadStoreHost WriteStoreHost ClipboardCopyHost SecureAvailableHost SecureSavedHost \
    SecureRequestHost SecureForgetHost SecurePollHost; do
    binds="$binds --bind app_context:$name=pass_state_host:$name"
done
"$ziran" bundle $args --entry pass_state_test:PassStateAnswer $binds \
    -o build/pass-state-test/portable.zib tests/pass_state_test.zi tests/pass_state_host.zi
test "$("$ziran" run build/pass-state-test/portable.zib)" = 42
echo 'Pass state: native and portable tests pass'
