# Draft: xyz.waozi.pass: rename to Werkzeug and update to 0.4.0

The app on F-Droid is now Werkzeug: Pass, Auth, Calculator and Clock in one
app. The current recipe still selects Pass 0.2.9 with its old name, website
and APK name. Update the existing package to the public Werkzeug 0.4.0
release, its links, description, screenshots and versioned APK name.
Preserve `xyz.waozi.pass` and the allowed signing certificate so existing
installations update in place.

The build uses the exact Ziran toolchain and nine dependency revisions from
the release lock, fetched as F-Droid source libraries before the build.
Package mappings and native/image paths use those managed sources. The old
0.2.9 build keeps its original reference APK filename.

Werkzeug 0.3.0 and 0.3.1 are not offered: their locks pin dependency commits
that upstream history no longer contains, so they cannot be rebuilt.

A full F-Droid source rebuild and reproducibility comparison remain pending.
Keep this request in draft until those checks pass.

- [Original merged submission](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/46404)
- [Existing successful reproducible build](https://monitor.f-droid.org/builds/log/xyz.waozi.pass/10)
- [Werkzeug 0.4.0 release](https://github.com/waozixyz/werk/releases/tag/v0.4.0)
