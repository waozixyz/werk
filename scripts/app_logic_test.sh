#!/bin/sh
# Auth's codes (RFC 6238 vectors) and export reading, and the Calculator's
# arithmetic, run as portable bundles like the apps themselves.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
ziran_root=$("$ziran" pkg path ziran)
mkdir -p build/app-logic-test
"$ziran" bundle --root . --module-path apps/auth --module-path shared --module-path "$ziran_root/std" \
    --entry totp_test:Run -o build/app-logic-test/totp.zib apps/auth/totp_test.zi
test "$("$ziran" run build/app-logic-test/totp.zib)" = 0
"$ziran" bundle --root . --module-path apps/auth --module-path shared --module-path "$ziran_root/std" \
    --entry exports_test:Run -o build/app-logic-test/exports.zib apps/auth/exports_test.zi
test "$("$ziran" run build/app-logic-test/exports.zib)" = 0
"$ziran" bundle --root . --module-path apps/calculator --module-path "$ziran_root/std" \
    --entry arithmetic_test:Run -o build/app-logic-test/arithmetic.zib apps/calculator/arithmetic_test.zi
test "$("$ziran" run build/app-logic-test/arithmetic.zib)" = 0
echo 'Auth codes and Calculator arithmetic tests pass'
