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
    env -u DISPLAY -u WAYLAND_DISPLAY WERKZEUG_DATA="$work/$dir" WERKZEUG_SYNC_SERVER="$server" \
        "$work/sync_e2e" "$@"
}
device a create
device a show "$work/code.txt" > "$work/show.log" 2>&1 &
shower=$!
device b join "$work/code.txt"
wait $shower || { cat "$work/show.log"; exit 1; }
device a remove
device b absent
# The server stored only sealed records: the test secret never reached it.
if grep -a -q GEZDGNBVGY3TQOJQ "$work/daochi.db"* 2>/dev/null; then
    echo "the server stored a secret in plain text"
    exit 1
fi
echo 'Werkzeug sync: account, connected device, record and removal through a local Daochi node'
