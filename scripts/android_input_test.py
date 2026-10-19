#!/usr/bin/env python3
"""Drive only a private emulator; never choose a connected phone implicitly."""
from pathlib import Path
import csv
import io
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

def find_label(word):
    shot("label")
    data = subprocess.check_output(["tesseract", str(output / "label.png"), "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1"],
                                   stderr=subprocess.DEVNULL, text=True)
    for item in csv.DictReader(io.StringIO(data), delimiter="\t"):
        if item["text"].strip().lower() == word.lower():
            return (int(item["left"]) + int(item["width"]) // 2,
                    int(item["top"]) + int(item["height"]) // 2)
    raise AssertionError(f"Could not find {word!r} in the private emulator")

def tap_label(word):
    tap(*find_label(word))

def dismiss_other_apps_not_responding():
    """A slow emulator can show another app's "isn't responding" dialog over
    Werkzeug, as CI's did for Settings. Close it, and stop that other app if
    the dialog stays. Werkzeug itself must never be the one hanging."""
    shell("am", "broadcast", "-a", "android.intent.action.CLOSE_SYSTEM_DIALOGS", check=False)
    for _ in range(3):
        hung = set(re.findall(r"Application Not Responding: ([\w.]+)", shell("dumpsys", "window", "windows")))
        if not hung: return
        assert package not in hung, "Werkzeug stopped responding"
        shell("am", "broadcast", "-a", "android.intent.action.CLOSE_SYSTEM_DIALOGS", check=False)
        time.sleep(1)
        if set(re.findall(r"Application Not Responding: ([\w.]+)", shell("dumpsys", "window", "windows"))):
            for name in hung: shell("am", "force-stop", name, check=False)
            time.sleep(1)
    raise AssertionError("Another app's dialog kept covering Werkzeug")

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
    # Android 12 and older name inset sources ITYPE_STATUS_BAR and so on.
    status = re.search(r"type=(?:statusBars|ITYPE_STATUS_BAR) frame=\[0,0\]\[\d+,(\d+)\]", dump)
    # A display cutout taller than the status bar pushes the app down further.
    cutout = re.search(r"type=(?:displayCutout|ITYPE_[A-Z_]*CUTOUT[A-Z_]*) frame=\[0,0\]\[\d+,(\d+)\]", dump)
    navigation = re.search(r"type=(?:navigationBars|ITYPE_NAVIGATION_BAR) frame=\[0,(\d+)\]\[\d+,(\d+)\]", dump)
    top = max(int(status.group(1)) if status else 0, int(cutout.group(1)) if cutout else 0)
    bottom = int(navigation.group(1)) if navigation and int(navigation.group(2)) == height else height
    return top, bottom

apk = root / "build/werk-android-emulator.apk"
check_apk(apk)
try:
    adb("install", "-r", str(apk))
    # This is the test emulator and only this package's fixture data is cleared.
    shell("pm", "clear", package)
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(2); alive(); dismiss_other_apps_not_responding(); shot("launch")
    size = shell("wm", "size").strip().split()[-1]
    width, height = map(int, size.split("x"))
    # Werkzeug scales by the screen density, as Android's dp do.
    densities = re.findall(r"density: (\d+)", shell("wm", "density"))
    zoom = int(densities[-1]) / 160
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
    time.sleep(1); alive(); dismiss_other_apps_not_responding()
    assert shell("run-as", package, "cat", "files/apps/pass/profiles.tsv") == expected
    assert shell("run-as", package, "stat", "-c", "%a", "files/apps/pass/profiles.tsv").strip() == "600"
    shot("persisted")
    # Profile's name is one of Werkzeug's own fields. Each letter must land
    # after the last, at the caret the keyboard reports.
    tap(int(28 * zoom), top + int(28 * zoom)); time.sleep(0.5)
    tap(width - int(60 * zoom), top + int(28 * zoom)); time.sleep(0.8); alive()
    # Self's profile card: the picture, then Name.
    tap(width // 2, top + int(357 * zoom)); type_text("Ada Lovelace")
    shot("profile-name")
    shell("input", "keyevent", "4"); time.sleep(0.3)
    # Leaving Profile saves it.
    tap(int(28 * zoom), top + int(28 * zoom)); time.sleep(0.5); alive()
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "name=Ada Lovelace\n" in settings, f"Profile name typed out of order: {settings!r}"
    tap(width - int(60 * zoom), top + int(28 * zoom)); time.sleep(0.8)
    # Self's Nodes section: the empty "Node address" field, then Add.
    tap_label("Node")
    type_text("https://sync.example.invalid:8443/")
    shell("input", "keyevent", "4"); time.sleep(1.2)
    # OCR misses Add's white label on the accent. It ends the row above
    # Appearance, wherever the keyboard left the page scrolled.
    _, appearance = find_label("Appearance")
    tap(width - int(81 * zoom), appearance - int(56 * zoom)); time.sleep(0.8)
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "node=https://sync.example.invalid:8443\n" in settings, "Custom node was not saved"
    assert adb("shell", "run-as", package, "test", "-f", "files/account/keys.txt", check=False).returncode != 0
    shot("custom-node")
    # Updating this same package preserves both the tool's files and the
    # profile. No owner phone is selected by this harness.
    shell("am", "force-stop", package)
    adb("install", "-r", str(apk))
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(1); alive(); dismiss_other_apps_not_responding()
    assert shell("run-as", package, "cat", "files/profile/settings.txt") == settings
    assert shell("run-as", package, "cat", "files/apps/pass/profiles.tsv") == expected
    shot("updated")
    print("Werkzeug Android: input, profiles, custom node and in-place package update preserved private data")
except BaseException:
    shot("failure")
    raise
