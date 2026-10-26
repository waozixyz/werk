#!/bin/sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
out_dir="$root_dir/build/site"

# werk.waozi.xyz is the web app itself. Downloads keep their addresses
# through _redirects, and the app's earlier /app/ address forwards here.
rm -rf "$out_dir"
mkdir -p "$out_dir"
for name in CNAME robots.txt sitemap.xml _redirects _headers manifest.webmanifest; do
	cp "$root_dir/web/site/$name" "$out_dir/$name"
done
cp -R "$root_dir/web/site/icons" "$out_dir/icons"
"${MAKE:-make}" -C "$root_dir" web-canvas
for name in index.html sw.js index.js index.wasm; do
	cp "$root_dir/build/web-app/$name" "$out_dir/$name"
done
cp "$root_dir/assets/fonts/emoji-OFL.txt" "$out_dir/emoji-OFL.txt"

test -s "$out_dir/index.wasm"
printf 'built site at %s\n' "$out_dir"
python3 - "$out_dir" <<'META'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
wasm = (root / "index.wasm").read_bytes()
wasm_name = "index-" + hashlib.sha256(wasm).hexdigest()[:16] + ".wasm"
(root / wasm_name).write_bytes(wasm)
loader = (root / "index.js").read_text()
assert loader.count('"index.wasm"') == 1, "Expected one Wasm URL in the generated loader"
loader = loader.replace('"index.wasm"', json.dumps(wasm_name))
js_name = "index-" + hashlib.sha256(loader.encode()).hexdigest()[:16] + ".js"
(root / js_name).write_text(loader)
(root / "index.js").write_text(loader)
html = (root / "index.html").read_text()
assert html.count('src="index.js"') == 1
(root / "index.html").write_text(html.replace('src="index.js"', 'src="' + js_name + '"'))
assets = ["./", js_name, wasm_name, "sw.js", "icons/icon-192.png", "icons/icon-512.png", "manifest.webmanifest", "assets.json"]
(root / "assets.json").write_text(json.dumps(assets) + "\n")
with (root / "_headers").open("a") as headers:
    for name in [js_name, wasm_name]:
        headers.write("\n/" + name + "\n  Cache-Control: public, max-age=31536000, immutable\n")
META
