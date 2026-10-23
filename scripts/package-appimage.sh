#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(sed -n '1p' "$root/VERSION")
arch=${APPIMAGE_ARCH:-$(uname -m)}
linuxdeploy=${LINUXDEPLOY:-linuxdeploy}
artifacts=${WERK_BUILD_DIR:-$root/build}
appdir="$root/build/package/appimage/werk.AppDir"
out="$root/build/release/werk-${version}-${arch}.AppImage"

test -n "$version"
rm -rf "$appdir"
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib/werk/apps" "$appdir/usr/share/applications" \
	"$appdir/usr/share/mime/packages" "$appdir/usr/share/metainfo" "$appdir/usr/share/icons/hicolor/512x512/apps" "$(dirname "$out")"
cp "$artifacts/werk" "$appdir/usr/bin/werk"
cp "$artifacts"/apps/*.zx "$appdir/usr/lib/werk/apps/"
cp "$artifacts/pfp.png" "$appdir/usr/lib/werk/pfp.png"
python3 "$root/scripts/install-launchers.py" --data-dir "$appdir/usr/share"
cp "$root/packaging/linux/werk-bundle.xml" "$appdir/usr/share/mime/packages/werk-bundle.xml"
cp "$root/packaging/linux/xyz.waozi.werk.appdata.xml" "$appdir/usr/share/metainfo/xyz.waozi.werk.appdata.xml"
cp "$root/assets/app/icon.png" "$root/build/package/appimage/werk.png"
run_dir=$(mktemp -d "$root/build/package/appimage/output.XXXXXX")
(cd "$run_dir" && ARCH="$arch" "$linuxdeploy" --appdir "$appdir" --desktop-file "$root/packaging/linux/xyz.waozi.werk.desktop" \
	--icon-file "$root/build/package/appimage/werk.png" --output appimage)
image=$(find "$run_dir" -maxdepth 1 -type f -name '*.AppImage' -print | head -n 1)
test -n "$image"
mv "$image" "$out"
chmod 0755 "$out"
printf 'built %s\n' "$out"
