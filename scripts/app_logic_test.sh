#!/bin/sh
# Auth's codes (RFC 6238 vectors) and export reading, and the Calculator's
# arithmetic, run as portable bundles like the apps themselves.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
case "$ziran" in
    /*) ;;
    */*) ziran="$root/$ziran" ;;
esac
ziran_root=$("$ziran" pkg path ziran)
# Test Auth in its canonical package graph, as the portable app builds.
auth=$("$ziran" pkg path auth)
mkdir -p build/app-logic-test
for name in totp exports; do
    (cd "$auth" && "$ziran" bundle --project --locked --entry "${name}_test:Run" \
        -o "$root/build/app-logic-test/$name.zx" "tests/${name}_test.zi")
    test "$("$ziran" run "build/app-logic-test/$name.zx")" = 0
done
"$ziran" bundle --project --root . --entry arithmetic_test:Run \
    -o build/app-logic-test/arithmetic.zx apps/calculator/arithmetic_test.zi
test "$("$ziran" run build/app-logic-test/arithmetic.zx)" = 0
set -- --project --root . --module-path tests --entry calculator_input_test:main
"$ziran" bundle "$@" --define KRYON_HOSTED_UI \
    --bind-host calculator_input_test \
    -o build/app-logic-test/input.zx tests/calculator_input_test.zi
test "$("$ziran" run build/app-logic-test/input.zx)" = 42
"$ziran" build "$@" --target=c -o build/app-logic-test/input-c tests/calculator_input_test.zi
${CC:-cc} -std=c99 -O2 -ffunction-sections -fdata-sections -Wl,--gc-sections \
    -I"$ziran_root/include" -Ibuild/app-logic-test/input-c build/app-logic-test/input-c/*.c -lm \
    -o build/app-logic-test/input-native
status=0
build/app-logic-test/input-native || status=$?
test "$status" = 42
echo 'Auth codes, Calculator arithmetic and batched keyboard commands pass'
