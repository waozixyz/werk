#!/usr/bin/env python3
"""Drive only a private emulator; never choose a connected phone implicitly."""
from pathlib import Path
import os
import re
import subprocess
import time
from android_apk_check import check_apk

root = Path(__file__).resolve().parents[1]
output = root / "build/android-input"
output.mkdir(parents=True, exist_ok=True)
serial = os.environ.get("WERK_ANDROID_EMULATOR")
if not serial:
    devices = subprocess.check_output(["adb", "devices"], text=True).splitlines()
    serial = next((line.split()[0] for line in devices if line.startswith("emulator-") and line.split()[-1] == "device"), None)
if not serial or not serial.startswith("emulator-"):
    raise SystemExit("Android input tests require a private emulator")
package = "xyz.waozi.pass"

def adb(*arguments, check=True):
    return subprocess.run(["adb", "-s", serial, *arguments], check=check, capture_output=True)

def shell(*arguments, check=True):
    return adb("shell", *arguments, check=check).stdout.decode()

def shot(name):
    (output / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p").stdout)

def alive():
    if not shell("pidof", package, check=False).strip():
        details = adb("logcat", "-d", "-b", "crash").stdout.decode()
        raise AssertionError("Werkzeug stopped in the private emulator:\n" + details[-6000:])
    activities = shell("dumpsys", "activity", "activities")
    # mResumedActivity before Android 13, ResumedActivity from then on.
    resumed = next((line for line in activities.splitlines()
                    if line.strip().startswith(("mResumedActivity:", "ResumedActivity:"))), "")
    assert package in resumed, f"Werkzeug activity closed or lost foreground: {resumed}"

def tap(x, y):
    shell("input", "tap", str(x), str(y)); time.sleep(0.25)

def type_text(text):
    shell("input", "text", text.replace(" ", "%s")); time.sleep(0.3)

def system_bars(height):
    """The app's first and last rows in pixels: Werkzeug keeps its content
    between the status bar and the navigation bar."""
    dump = shell("dumpsys", "window")
    status = re.search(r"type=statusBars frame=\[0,0\]\[\d+,(\d+)\]", dump)
    navigation = re.search(r"type=navigationBars frame=\[0,(\d+)\]\[\d+,(\d+)\]", dump)
    top = int(status.group(1)) if status else 0
    bottom = int(navigation.group(1)) if navigation and int(navigation.group(2)) == height else height
    return top, bottom

apk = root / "build/werk-android-emulator.apk"
check_apk(apk)
try:
    adb("install", "-r", str(apk))
    # This is the test emulator and only this package's fixture data is cleared.
    shell("pm", "clear", package)
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(2); alive(); shot("launch")
    size = shell("wm", "size").strip().split()[-1]
    width, height = map(int, size.split("x"))
    zoom = width / 390
    top, bottom = system_bars(height)
    # Pass's tile on the home screen, then Pass below Werkzeug's 56-unit bar.
    tap(int(127 * zoom), top + int(132 * zoom)); time.sleep(0.5); alive(); shot("pass")
    bar = 56
    tap(int(90 * zoom), top + int((55 + bar) * zoom)); type_text("example.com")
    assert "mInputShown=true" in shell("dumpsys", "input_method"), "Soft keyboard did not open"
    tap(int(90 * zoom), top + int((130 + bar) * zoom)); type_text("alice")
    tap(int(90 * zoom), top + int((205 + bar) * zoom)); type_text("test master")
    shot("keyboard")
    shell("input", "keyevent", "4"); time.sleep(0.4); alive()
    tap(width // 2, bottom - int(35 * zoom))
    tap(int(90 * zoom), top + int((55 + bar) * zoom)); type_text("Android test")
    shell("input", "keyevent", "4"); time.sleep(0.3)
    tap(int(100 * zoom), top + int((105 + bar) * zoom))
    expected = "Android test\texample.com\talice\t16\t1\t1\t1\t1\t1\t\n"
    saved = shell("run-as", package, "cat", "files/apps/pass/profiles.tsv")
    assert saved == expected, f"Profile input/persistence mismatch: {saved!r}"
    assert "test master" not in saved
    # Generate from the saved profile and copy it.
    tap(int(100 * zoom), top + int((210 + bar) * zoom))
    time.sleep(0.5)
    tap(int(100 * zoom), bottom - int(119 * zoom))  # Copy, at the bottom of the scrolled form
    shot("generated")
    tap(width // 2, bottom - int(35 * zoom))
    tap(int(90 * zoom), top + int((55 + bar) * zoom))
    shell("input", "keyevent", "123")  # Move to the end.
    shell("input", "keyevent", *("67" for _ in "Android test"))
    # Type the reference password as the new name. Pasting the copy works
    # through the keyboard's clipboard suggestion, which Gboard offers only
    # once per clip, so it is not automated here.
    type_text("dEeEDu7/b27L#r\\<\\&")
    time.sleep(0.5)
    shell("input", "keyevent", "4"); time.sleep(0.3)
    tap(int(100 * zoom), top + int((105 + bar) * zoom))
    password = "dEeEDu7/b27L#r<&"  # Independent LessPass reference.
    expected += password + "\texample.com\talice\t16\t1\t1\t1\t1\t1\t\n"
    assert shell("run-as", package, "cat", "files/apps/pass/profiles.tsv") == expected, "Android second profile mismatch"
    shell("am", "force-stop", package)
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(1); alive()
    assert shell("run-as", package, "cat", "files/apps/pass/profiles.tsv") == expected
    assert shell("run-as", package, "stat", "-c", "%a", "files/apps/pass/profiles.tsv").strip() == "600"
    shot("persisted")
    # Profile's name is one of Werkzeug's own fields. Each letter must land
    # after the last, at the caret the keyboard reports.
    tap(int(28 * zoom), top + int(28 * zoom)); time.sleep(0.5)
    tap(width - int(60 * zoom), top + int(28 * zoom)); time.sleep(0.8); alive()
    tap(width // 2, top + int(232 * zoom)); type_text("Ada Lovelace")
    shot("profile-name")
    shell("input", "keyevent", "4"); time.sleep(0.3)
    # Leaving Profile saves it.
    tap(int(28 * zoom), top + int(28 * zoom)); time.sleep(0.5); alive()
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "name=Ada Lovelace\n" in settings, f"Profile name typed out of order: {settings!r}"
    print("Werkzeug Android: home, Pass keyboard, masked master, profiles, generation, restart and profile name pass")
except BaseException:
    shot("failure")
    raise
