#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(sed -n '1p' "$root/VERSION")
arch=${APPIMAGE_ARCH:-$(uname -m)}
linuxdeploy=${LINUXDEPLOY:-linuxdeploy}
appdir="$root/build/package/appimage/werkzeug.AppDir"
out="$root/build/release/werkzeug-${version}-${arch}.AppImage"

test -n "$version"
rm -rf "$appdir"
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib/werkzeug/apps" "$appdir/usr/share/applications" \
	"$appdir/usr/share/metainfo" "$appdir/usr/share/icons/hicolor/512x512/apps" "$(dirname "$out")"
cp "$root/build/werkzeug" "$appdir/usr/bin/werkzeug"
cp "$root"/build/apps/*.zib "$appdir/usr/lib/werkzeug/apps/"
cp "$root/build/pfp.png" "$appdir/usr/lib/werkzeug/pfp.png"
cp "$root/packaging/linux/xyz.waozi.werkzeug.desktop" "$appdir/usr/share/applications/xyz.waozi.werkzeug.desktop"
cp "$root/packaging/linux/xyz.waozi.werkzeug.appdata.xml" "$appdir/usr/share/metainfo/xyz.waozi.werkzeug.appdata.xml"
cp "$root/assets/app/icon.png" "$appdir/usr/share/icons/hicolor/512x512/apps/werkzeug.png"
cp "$root/assets/app/icon.png" "$root/build/package/appimage/werkzeug.png"
rm -f "$root"/Werkzeug-*.AppImage "$root"/werkzeug-*.AppImage
ARCH="$arch" "$linuxdeploy" --appdir "$appdir" --desktop-file "$root/packaging/linux/xyz.waozi.werkzeug.desktop" \
	--icon-file "$root/build/package/appimage/werkzeug.png" --output appimage
image=$(find "$root" -maxdepth 1 -type f -name '*.AppImage' -print | head -n 1)
test -n "$image"
mv "$image" "$out"
chmod 0755 "$out"
printf 'built %s\n' "$out"
