#!/usr/bin/env python3
"""Validate a Werkzeug Play candidate without uploading it."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from android_apk_check import elf_section_names

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("bundle", type=Path)
parser.add_argument("--bundletool", type=Path, required=True)
parser.add_argument("--version", required=True)
parser.add_argument("--unsigned", action="store_true", help="Validate structure only; this candidate cannot be uploaded")
args = parser.parse_args()
bundle = args.bundle.resolve(strict=True)
tool = args.bundletool.resolve(strict=True)
subprocess.run(["java", "-jar", str(tool), "validate", "--bundle=" + str(bundle)],
               check=True, stdout=subprocess.DEVNULL)
xml = subprocess.check_output(["java", "-jar", str(tool), "dump", "manifest", "--bundle=" + str(bundle)], text=True)
manifest = ET.fromstring(xml)
android = "{http://schemas.android.com/apk/res/android}"
assert manifest.get("package") == "xyz.waozi.pass", "Werkzeug updates the existing Pass package"
assert manifest.get(android + "versionName") == args.version
assert int(manifest.find("uses-sdk").get(android + "targetSdkVersion")) >= 36
assert manifest.find("application").get(android + "debuggable", "false") == "false"
if not args.unsigned:
    signed = subprocess.check_output(["jarsigner", "-verify", str(bundle)], text=True,
                                     env=dict(os.environ, LC_ALL="C"))
    assert "jar verified." in signed, "The Play candidate must be signed"
    certificates = subprocess.check_output(["keytool", "-printcert", "-jarfile", str(bundle)], text=True,
                                          env=dict(os.environ, LC_ALL="C"))
    fingerprints = re.findall(r"SHA256:\s*([A-Fa-f0-9:]+)", certificates)
    expected = "1ac82db5bc8f742b8161fdd7083cefc16b39524dce7d103a7eb7f1ee19589c2d"
    assert fingerprints and {x.replace(":", "").lower() for x in fingerprints} == {expected}, "Bundle signer differs from the existing release key"
with zipfile.ZipFile(bundle) as archive:
    expected_bundles = {f"base/assets/apps/{app}.zx" for app in ("pass", "auth", "calculator", "clock", "workbook", "entity", "apps")}
    actual_bundles = {name for name in archive.namelist() if name.startswith("base/assets/apps/") and not name.endswith("/")}
    assert actual_bundles == expected_bundles, f"Stale or missing app bundles: {actual_bundles ^ expected_bundles}"
    for name in expected_bundles:
        assert archive.read(name)[:4] == b"ZX\0\0", f"Obsolete bundle format: {name}"
    for font in ("ui.ttf", "emoji.ttf"):
        assert "base/assets/fonts/" + font in archive.namelist()
    abis = {x.split("/")[2] for x in archive.namelist() if x.startswith("base/lib/") and x.endswith(".so")}
    assert abis == {"arm64-v8a", "armeabi-v7a"}
    root = Path(__file__).resolve().parents[1] / "build/play-verify"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        for name in archive.namelist():
            if not name.startswith("base/lib/arm64-v8a/") or not name.endswith(".so"): continue
            library = Path(directory) / Path(name).name
            library.write_bytes(archive.read(name))
            assert ".note.gnu.build-id" not in set(elf_section_names(library.read_bytes())), "Native library contains a build-path-dependent build ID"
            headers = subprocess.check_output(["readelf", "-lW", str(library)], text=True)
            loads = [line.split() for line in headers.splitlines() if line.strip().startswith("LOAD ")]
            assert loads and all(int(parts[-1], 16) >= 16384 for parts in loads), "Native library needs 16 KB alignment"
print("Werkzeug " + args.version + ": " + ("unsigned structure verified; signing pending" if args.unsigned else "signed Play bundle verified"))
