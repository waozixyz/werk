#!/usr/bin/env python3
"""Reject handwritten application implementations outside Ziran."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
tracked = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
bad = []
for name in tracked:
    if not name or not (root / name).is_file():
        continue
    path = Path(name)
    if path.suffix in {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".kry", ".java", ".kt", ".go", ".rs", ".swift", ".m", ".mm", ".zig"}:
        bad.append(name)
    if name.startswith("web/site/") and path.suffix == ".js":
        bad.append(name)
if bad:
    raise SystemExit("Non-Ziran app implementation:\n" + "\n".join(bad))
manifest = (root / "droid/app/src/main/AndroidManifest.xml").read_text()
assert 'android:hasCode="true"' in manifest
assert 'android:name="android.app.NativeActivity"' in manifest
# The only Java comes from Kryon's shared account consent components.
gradle = (root / "droid/app/build.gradle").read_text()
assert "templates/android-account-handoff.gradle" in gradle
android = (root / "src/android_glue.zi").read_text()
assert "Handoff.AccountHandoffJniOnLoad(vm)" in android
# Fingerprint unlock for the saved master password, and the network only for
# sync, which stays off until the owner sets up an account.
import re
# The launcher uses the same reviewed bytes at build time and at runtime.
home = (root / "src/home.zi").read_text()
controller = re.search(r'AppsControllerSha256 :: "([a-f0-9]{64})"', home)
assert controller and controller[1] == (root / "apps-controller.sha256").read_text().strip()
permissions = set(re.findall(r'uses-permission android:name="([^"]+)"', manifest))
assert permissions <= {"android.permission.USE_BIOMETRIC", "android.permission.USE_FINGERPRINT",
                       "android.permission.INTERNET"}, permissions
print("All maintained Werkzeug application implementations are Ziran")
