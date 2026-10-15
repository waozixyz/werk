#!/usr/bin/env python3
"""Check real F-Droid/debug artifacts without installing anything."""
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
fdroid, debug, emulator = map(Path, sys.argv[1:])
identity = None
for path, expected_abis in [(fdroid, {"armeabi-v7a", "arm64-v8a"}),
                            (debug, {"armeabi-v7a", "arm64-v8a"}),
                            (emulator, {"x86_64"})]:
    badging = subprocess.check_output(["aapt", "dump", "badging", str(path)], text=True)
    package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    assert package, f"{path}: no package identity"
    current = package.groups()
    assert current[0] == "xyz.waozi.pass", "Updating must preserve Pass's Android ID"
    assert current[2] == (root / "VERSION").read_text().strip(), "Channel added a version suffix"
    if identity is None:
        identity = current
    assert current == identity, "F-Droid and direct builds have different identities"
    assert "application-label:'Werkzeug'" in badging
    permissions = subprocess.check_output(["aapt", "dump", "permissions", str(path)], text=True)
    assert not any(name in permissions for name in
                   ["REQUEST_INSTALL_PACKAGES", "INSTALL_PACKAGES", "DELETE_PACKAGES"]), "App can compete with its installer"
    with ZipFile(path) as archive:
        abis = {name.split('/')[1] for name in archive.namelist()
                if name.startswith('lib/') and name.endswith('/libmain.so')}
        assert abis == expected_abis, f"{path}: wrong ABIs {abis}"
        assert archive.read("assets/icon.png") == (root / "assets/app/icon.png").read_bytes(), "Stale app logo"
    signature = subprocess.run(["apksigner", "verify", str(path)], capture_output=True)
    assert (signature.returncode != 0) == (path == fdroid), "F-Droid must be unsigned; debug must be signed"
print("Android distribution: matching package/version, Werkzeug label/logo, correct ABIs, builder signing and no installer permissions")
