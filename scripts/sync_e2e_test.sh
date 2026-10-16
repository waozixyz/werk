#!/bin/sh
# Account sync between two Werkzeug devices through a local Daochi node:
# create an account with an Auth record, connect a second device with the
# shown code, receive the record there, then remove it and see the removal
# arrive. Needs the Daochi checkout (DAOCHI_DIR) with its liboqs built.
set -eu
ziran=${1:?pass the ziran command}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
daochi=${DAOCHI_DIR:-$root/../../kryonlabs/daochi}
if [ ! -f "$daochi/go.mod" ]; then
    echo "sync e2e skipped: no Daochi checkout at $daochi"
    exit 0
fi
work=$root/build/sync-e2e
rm -rf "$work"
mkdir -p "$work/a" "$work/b"
oqs=$daochi/build/liboqs/install
make -C "$daochi" liboqs > /dev/null
(cd "$daochi" && CGO_ENABLED=1 GOFLAGS=-mod=mod CGO_CFLAGS="-I$oqs/include" CGO_LDFLAGS="-L$oqs/lib -loqs" \
    go build -o "$work/daochi" .)
"$ziran" build --project $(test -f ziran.local.toml || echo --locked) --root tests --target=c --entry sync_e2e:main \
    -o "$work/c" tests/sync_e2e.zi
monocypher=$("$ziran" pkg path monocypher)
make build/ziran/libziran.a build/liboqs/lib/liboqs.a > /dev/null
${CC:-cc} -std=c99 -O2 -Wno-unused-variable -I"$("$ziran" pkg path ziran)/include" -I"$work/c" \
    -I"$monocypher/src" -I"$monocypher/src/optional" "$work"/c/*.c \
    "$monocypher/src/monocypher.c" "$monocypher/src/optional/monocypher-ed25519.c" \
    build/ziran/libziran.a build/liboqs/lib/liboqs.a \
    $(pkg-config --libs sdl2 cairo freetype2 fontconfig pangocairo) -l:libcurl.so.4 -lm -lpthread \
    -o "$work/sync_e2e"

mkdir -p "$work/preferences"
for mode in preferences paused; do
    env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS -u WERK_SYNC_SERVER \
        WERK_DATA="$work/preferences" "$work/sync_e2e" "$mode"
done

port=$((20000 + $$ % 20000))
server=http://127.0.0.1:$port
secret=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
# A throwaway registry key for this node approves the werkzeug manifest.
registry=$(python3 -I scripts/register_daochi_app.py "$server" "$work/publisher.pem" "$work/registry.pem" \
    --new-registry --registry-public)
env -i PATH="$PATH" HOME="$work" DAOCHI_ADDR=127.0.0.1:$port DAOCHI_DB="$work/daochi.db" \
    DAOCHI_TOKEN_SECRET_HEX="$secret" DAOCHI_NODE_REGISTRY_PUBLIC_KEY_HEX="$registry" \
    "$work/daochi" > "$work/daochi.log" 2>&1 &
node=$!
trap 'kill $node 2>/dev/null || true' EXIT HUP INT TERM
tries=0
until curl -fsS "$server/readyz" > /dev/null 2>&1; do
    tries=$((tries + 1))
    if [ $tries -gt 100 ]; then
        echo "Daochi did not start:"
        tail -20 "$work/daochi.log"
        exit 1
    fi
    sleep 0.1
done

python3 -I scripts/register_daochi_app.py "$server" "$work/publisher.pem" "$work/registry.pem" > "$work/register.log"

device() {
    dir=$1
    shift
    env -u DISPLAY -u WAYLAND_DISPLAY WERK_DATA="$work/$dir" WERK_SYNC_SERVER="$server" \
        "$work/sync_e2e" "$@"
}
device a create
device a show "$work/code.txt" > "$work/show.log" 2>&1 &
shower=$!
device b join "$work/code.txt"
wait $shower || { cat "$work/show.log"; exit 1; }
device a remove
device b absent
# The same through `werk` without a window: one device creates the account
# and imports a link, another connects with the code `werk sync show`
# prints, receives the account with its website and removes it again.
make build/werk > /dev/null
werk() {
    dir=$1
    shift
    env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS WERK_DATA="$work/$dir" \
        WERK_SYNC_SERVER="$server" "$root/build/werk" "$@"
}
mkdir -p "$work/werk-a" "$work/werk-b"
werk werk-a sync create > /dev/null
printf '%s\n' 'otpauth://totp/Test:carol?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=Test&sites=example.com' |
    werk werk-a auth import > /dev/null
werk werk-a sync show > "$work/werk-show.log" 2>&1 &
shower=$!
tries=0
until grep -q 'other device: ' "$work/werk-show.log"; do
    tries=$((tries + 1))
    if [ $tries -gt 100 ]; then
        cat "$work/werk-show.log"
        exit 1
    fi
    sleep 0.1
done
sed -n 's/.*other device: //p' "$work/werk-show.log" | werk werk-b sync join > /dev/null
wait $shower || { cat "$work/werk-show.log"; exit 1; }
listed=$(werk werk-b auth list)
case $listed in
*'"issuer":"Test","account":"carol","sites":["example.com"]'*) ;;
*) echo "the connected device did not receive the account: $listed"; exit 1 ;;
esac
id=$(printf '%s' "$listed" | sed -n 's/.*"id":"\([0-9a-f]*\)".*/\1/p')
werk werk-b auth remove "$id" > /dev/null
test "$(werk werk-a auth list)" = '[]' || { echo 'the removal did not reach the first device'; exit 1; }

# A Daochi account key, as Inbe exports it, signs devices in to the same
# records: one with the plain key, one with the passphrase-protected copy.
env -u DISPLAY -u WAYLAND_DISPLAY "$work/sync_e2e" keyfiles "$work/account.key" "$work/account-locked.key" \
    'fixture passphrase' > /dev/null
mkdir -p "$work/werk-c" "$work/werk-d" "$work/werk-e"
werk werk-c sync key "$work/account.key" > /dev/null
printf '%s\n' 'otpauth://totp/Keyed:dave?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=Keyed' |
    werk werk-c auth import > /dev/null
if printf 'wrong\n' | werk werk-e sync key "$work/account-locked.key" > /dev/null 2>&1; then
    echo 'a wrong passphrase signed in'
    exit 1
fi
printf 'fixture passphrase\n' | werk werk-d sync key "$work/account-locked.key" > /dev/null
case $(werk werk-d auth list) in
*'"issuer":"Keyed","account":"dave"'*) ;;
*) echo 'the device signed in with the key did not receive the account'; exit 1 ;;
esac

# The server stored only sealed records: the test secret never reached it.
if grep -a -q GEZDGNBVGY3TQOJQ "$work/daochi.db"* 2>/dev/null; then
    echo "the server stored a secret in plain text"
    exit 1
fi
echo 'Werkzeug sync: account, connected device, record and removal through a local Daochi node, also with werk sync, werk auth and an account key'
