# Draft: xyz.waozi.pass: rename to Werkzeug and update to 0.3.1

Pass became Werkzeug in 0.3.0. The current F-Droid recipe still selects Pass
0.2.9 and its old website and APK name. Update the existing package to the
public Werkzeug 0.3.1 release, current links and versioned APK name. Preserve
`xyz.waozi.pass` and the allowed signing certificate so existing installations
can update in place.

The new build uses the exact Ziran toolchain and seven dependency revisions
from the release lock, fetched as F-Droid source libraries before the build.
Package mappings and native/image paths use those managed sources. The old
0.2.9 build retains its original reference APK filename.

Metadata lint and formatting checks pass, and all source pins match the
public release lock. The prebuild commands were executed against the release
CMake/Gradle inputs and the generated mappings and paths checked. The public
0.3.1 universal APK was verified: package `xyz.waozi.pass`, versionCode 13,
label Werkzeug, both ARM ABIs and the existing allowed signing certificate.

A full F-Droid source rebuild and reproducibility comparison remain pending.
Keep this request in draft until those checks pass. Local 0.4.0 development
changes are not part of this recipe's release reference.

- [Original merged submission](https://gitlab.com/fdroid/fdroiddata/-/merge_requests/46404)
- [Existing successful reproducible build](https://monitor.f-droid.org/builds/log/xyz.waozi.pass/10)
- [Public renamed release](https://github.com/waozixyz/werk/releases/tag/v0.3.1)
