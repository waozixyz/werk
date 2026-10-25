#!/bin/sh
# Auth's codes (RFC 6238 vectors) and export reading, and the Calculator's
# arithmetic, run as portable bundles like the apps themselves.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
ziran_root=$("$ziran" pkg path ziran)
kryon=$("$ziran" pkg path kryon)
mingcute=$("$ziran" pkg path mingcute)
# Auth runs its own tests from its package, with the hashes from crypto.
auth=$("$ziran" pkg path auth)
crypto=$("$ziran" pkg path crypto)
mkdir -p build/app-logic-test
"$ziran" bundle --root "$auth" --module-path "$auth/src" --module-path "crypto=$crypto/src" --module-path "$ziran_root/std" \
    --entry totp_test:Run -o build/app-logic-test/totp.zx "$auth/tests/totp_test.zi"
test "$("$ziran" run build/app-logic-test/totp.zx)" = 0
"$ziran" bundle --root "$auth" --module-path "$auth/src" --module-path "crypto=$crypto/src" --module-path "$ziran_root/std" \
    --entry exports_test:Run -o build/app-logic-test/exports.zx "$auth/tests/exports_test.zi"
test "$("$ziran" run build/app-logic-test/exports.zx)" = 0
"$ziran" bundle --root . --module-path apps/calculator --module-path "$ziran_root/std" \
    --entry arithmetic_test:Run -o build/app-logic-test/arithmetic.zx apps/calculator/arithmetic_test.zi
test "$("$ziran" run build/app-logic-test/arithmetic.zx)" = 0
set -- --root tests --module-path apps/calculator \
    --module-path "kryon=$kryon/src/backend" --module-path "kryon=$kryon/src/ui" \
    --module-path "$kryon/src/ui" --module-path "$mingcute/src" --module-path "$ziran_root/std" \
    --entry calculator_input_test:main
"$ziran" bundle "$@" --define KRYON_HOSTED_UI \
    --bind app_context:AppKeyHost=calculator_input_test:AppKeyHost \
    --bind app_context:AppFieldInputHost=calculator_input_test:AppFieldInputHost \
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
