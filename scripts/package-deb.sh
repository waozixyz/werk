#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(sed -n '1p' "$root/VERSION")
arch=${DEB_ARCH:-$(dpkg --print-architecture)}
stage="$root/build/package/deb/werk"
out="$root/build/release"

test -n "$version"
rm -rf "$stage"
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/lib/werk/apps" "$stage/usr/share/applications" \
	"$stage/usr/share/metainfo" "$stage/usr/share/icons/hicolor/512x512/apps" "$stage/usr/share/doc/werk" "$out"
cp "$root/build/werk" "$stage/usr/bin/werk"
cp "$root"/build/apps/*.zib "$stage/usr/lib/werk/apps/"
cp "$root/build/pfp.png" "$stage/usr/lib/werk/pfp.png"
cp "$root/packaging/linux/xyz.waozi.werk.desktop" "$stage/usr/share/applications/xyz.waozi.werk.desktop"
cp "$root/packaging/linux/xyz.waozi.werk.appdata.xml" "$stage/usr/share/metainfo/xyz.waozi.werk.appdata.xml"
cp "$root/assets/app/icon.png" "$stage/usr/share/icons/hicolor/512x512/apps/werk.png"
cp "$root/LICENSE" "$root/README.md" "$stage/usr/share/doc/werk/"
find "$stage" -type d -exec chmod 0755 {} \;
chmod 0755 "$stage/usr/bin/werk"
find "$stage/usr/share" "$stage/usr/lib" -type f -exec chmod 0644 {} \;
installed=$(du -sk "$stage" | awk '{print $1}')
cat > "$stage/DEBIAN/control" <<CONTROL
Package: werk
Version: $version
Architecture: $arch
Maintainer: Waozi <waozi@proton.me>
Installed-Size: $installed
Depends: libc6, libsdl2-2.0-0, libcairo2, libfreetype6, libfontconfig1, libpangocairo-1.0-0, libgtk-3-0, libx11-6
Section: utils
Priority: optional
Homepage: https://werk.waozi.xyz/
Description: small private tools: passwords, two-factor codes, calculator, clock
 Pass derives repeatable passwords locally without a password database, Auth
 shows two-factor sign-in codes, and Calculator and Clock cover everyday sums
 and time. Everything stays on the device.
CONTROL
dpkg-deb --root-owner-group --build "$stage" "$out/werk_${version}_${arch}.deb"
