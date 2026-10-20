#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(sed -n '1p' "$root/VERSION")
arch=${APPIMAGE_ARCH:-$(uname -m)}
linuxdeploy=${LINUXDEPLOY:-linuxdeploy}
appdir="$root/build/package/appimage/werk.AppDir"
out="$root/build/release/werk-${version}-${arch}.AppImage"

test -n "$version"
rm -rf "$appdir"
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib/werk/apps" "$appdir/usr/share/applications" \
	"$appdir/usr/share/mime/packages" "$appdir/usr/share/metainfo" "$appdir/usr/share/icons/hicolor/512x512/apps" "$(dirname "$out")"
cp "$root/build/werk" "$appdir/usr/bin/werk"
cp "$root"/build/apps/*.zib "$appdir/usr/lib/werk/apps/"
cp "$root/build/pfp.png" "$appdir/usr/lib/werk/pfp.png"
cp "$root/packaging/linux/xyz.waozi.werk.desktop" "$appdir/usr/share/applications/xyz.waozi.werk.desktop"
cp "$root/packaging/linux/werk-bundle.xml" "$appdir/usr/share/mime/packages/werk-bundle.xml"
cp "$root/packaging/linux/xyz.waozi.werk.appdata.xml" "$appdir/usr/share/metainfo/xyz.waozi.werk.appdata.xml"
cp "$root/assets/app/icon.png" "$appdir/usr/share/icons/hicolor/512x512/apps/werk.png"
cp "$root/assets/app/icon.png" "$root/build/package/appimage/werk.png"
rm -f "$root"/Werkzeug-*.AppImage "$root"/werk-*.AppImage
ARCH="$arch" "$linuxdeploy" --appdir "$appdir" --desktop-file "$root/packaging/linux/xyz.waozi.werk.desktop" \
	--icon-file "$root/build/package/appimage/werk.png" --output appimage
image=$(find "$root" -maxdepth 1 -type f -name '*.AppImage' -print | head -n 1)
test -n "$image"
mv "$image" "$out"
chmod 0755 "$out"
printf 'built %s\n' "$out"
