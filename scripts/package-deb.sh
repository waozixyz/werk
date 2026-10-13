#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(sed -n '1p' "$root/VERSION")
arch=${DEB_ARCH:-$(dpkg --print-architecture)}
stage="$root/build/package/deb/werkzeug"
out="$root/build/release"

test -n "$version"
rm -rf "$stage"
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/lib/werkzeug/apps" "$stage/usr/share/applications" \
	"$stage/usr/share/metainfo" "$stage/usr/share/icons/hicolor/512x512/apps" "$stage/usr/share/doc/werkzeug" "$out"
cp "$root/build/werkzeug" "$stage/usr/bin/werkzeug"
cp "$root"/build/apps/*.zib "$stage/usr/lib/werkzeug/apps/"
cp "$root/build/pfp.png" "$stage/usr/lib/werkzeug/pfp.png"
cp "$root/packaging/linux/xyz.waozi.werkzeug.desktop" "$stage/usr/share/applications/xyz.waozi.werkzeug.desktop"
cp "$root/packaging/linux/xyz.waozi.werkzeug.appdata.xml" "$stage/usr/share/metainfo/xyz.waozi.werkzeug.appdata.xml"
cp "$root/assets/app/icon.png" "$stage/usr/share/icons/hicolor/512x512/apps/werkzeug.png"
cp "$root/LICENSE" "$root/README.md" "$stage/usr/share/doc/werkzeug/"
find "$stage" -type d -exec chmod 0755 {} \;
chmod 0755 "$stage/usr/bin/werkzeug"
find "$stage/usr/share" "$stage/usr/lib" -type f -exec chmod 0644 {} \;
installed=$(du -sk "$stage" | awk '{print $1}')
cat > "$stage/DEBIAN/control" <<CONTROL
Package: werkzeug
Version: $version
Architecture: $arch
Maintainer: Waozi <waozi@proton.me>
Installed-Size: $installed
Depends: libc6, libsdl2-2.0-0, libcairo2, libfreetype6, libfontconfig1, libpangocairo-1.0-0
Section: utils
Priority: optional
Homepage: https://pass.waozi.xyz/
Description: small private tools: passwords, two-factor codes, calculator, clock
 Pass derives repeatable passwords locally without a password database, Auth
 shows two-factor sign-in codes, and Calculator and Clock cover everyday sums
 and time. Everything stays on the device.
CONTROL
dpkg-deb --root-owner-group --build "$stage" "$out/werkzeug_${version}_${arch}.deb"
