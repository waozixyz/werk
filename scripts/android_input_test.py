#!/usr/bin/env python3
"""Drive only a private emulator; never choose a connected phone implicitly."""
from pathlib import Path
import os
import re
import subprocess
import time
from android_apk_check import check_apk
from android_labels import label_position

root = Path(__file__).resolve().parents[1]
output = root / "build/android-input"
output.mkdir(parents=True, exist_ok=True)
serial = os.environ.get("WERK_ANDROID_EMULATOR")
if not serial and not os.environ.get("CI"):
    raise SystemExit("Set WERK_ANDROID_EMULATOR to your own private test emulator")
if not serial:
    devices = subprocess.check_output(["adb", "devices"], text=True).splitlines()
    serial = next((line.split()[0] for line in devices if line.startswith("emulator-") and line.split()[-1] == "device"), None)
if not serial or not serial.startswith("emulator-"):
    raise SystemExit("Android input tests require a private emulator")
package = "xyz.waozi.pass"

def adb(*arguments, check=True, input=None):
    return subprocess.run(["adb", "-s", serial, *arguments], check=check, capture_output=True, input=input, timeout=90)

def shell(*arguments, check=True):
    return adb("shell", *arguments, check=check).stdout.decode()

def shot(name):
    (output / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p").stdout)

def find_label(word, timeout=15):
    deadline = time.monotonic() + timeout
    while True:
        shot("label")
        position = label_position(output / "label.png", word)
        if position is not None:
            return position
        if time.monotonic() >= deadline:
            raise AssertionError(f"Could not find {word!r} in the private emulator")
        time.sleep(0.3)

def tap_label(word):
    tap(*find_label(word))

def scroll_to_label(word, direction="down"):
    hide_keyboard()
    for attempt in range(7):
        try:
            return find_label(word, timeout=2)
        except AssertionError:
            if attempt == 6:
                raise
        upper = top + int(150 * zoom)
        lower = bottom - int(80 * zoom)
        start, end = (lower, upper) if direction == "down" else (upper, lower)
        shell("input", "swipe", str(width // 2), str(start), str(width // 2), str(end), "450")
        time.sleep(PAUSE)

def dismiss_other_apps_not_responding():
    """A slow emulator can show an "isn't responding" dialog for another app,
    the system or Werkzeug over Werkzeug, as CI's did. Choose Wait, found
    through the accessibility tree. A real hang does not recover, so the
    next assertion still fails."""
    for _ in range(6):
        dumped = adb("shell", "uiautomator", "dump", "/sdcard/werk-ui.xml", check=False)
        tree = shell("cat", "/sdcard/werk-ui.xml", check=False) if dumped.returncode == 0 else ""
        # The tree escapes the apostrophe in "isn't responding".
        if " responding" not in tree:
            return
        if "Werkzeug isn" in tree:
            print("warning: the emulator reported Werkzeug slow to respond; waiting")
        wait = re.search(r'text="Wait"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tree)
        if wait:
            left, top_edge, right, bottom_edge = map(int, wait.groups())
            tap((left + right) // 2, (top_edge + bottom_edge) // 2)
        time.sleep(3)
    raise AssertionError("An \"isn't responding\" dialog kept covering Werkzeug")

def alive():
    if not shell("pidof", package, check=False).strip():
        details = adb("logcat", "-d", "-b", "crash").stdout.decode()
        raise AssertionError("Werkzeug stopped in the private emulator:\n" + details[-6000:])
    activities = shell("dumpsys", "activity", "activities")
    # mResumedActivity before Android 13, ResumedActivity from then on.
    resumed = next((line for line in activities.splitlines()
                    if line.strip().startswith(("mResumedActivity:", "ResumedActivity:"))), "")
    assert package in resumed, f"Werkzeug activity closed or lost foreground: {resumed}"

# CI's software-rendered emulator needs longer to apply each step.
PAUSE = 1.0 if os.environ.get("CI") else 0.25

def tap(x, y):
    shell("input", "tap", str(x), str(y)); time.sleep(PAUSE)

def type_text(text):
    shell("input", "text", text.replace(" ", "%s")); time.sleep(PAUSE + 0.05)

def hide_keyboard():
    if "mInputShown=true" in shell("dumpsys", "input_method"):
        shell("input", "keyevent", "4")
        for _ in range(20):
            time.sleep(0.15)
            if "mInputShown=true" not in shell("dumpsys", "input_method"):
                return
        raise AssertionError("Soft keyboard did not close")


def fill_field(label, text):
    hide_keyboard()
    _, y = find_label(label)
    tap(int(90 * zoom), y + int(40 * zoom))
    type_text(text)


def system_bars(height):
    """The app's first and last rows in pixels: Werkzeug keeps its content
    between the status bar and the navigation bar."""
    dump = shell("dumpsys", "window")
    # Android 12 and older name inset sources ITYPE_STATUS_BAR and so on.
    status = re.search(r"type=(?:statusBars|ITYPE_STATUS_BAR).*?frame=\[0,0\]\[\d+,(\d+)\]", dump)
    # A display cutout taller than the status bar pushes the app down further.
    cutout = re.search(r"type=(?:displayCutout|ITYPE_[A-Z_]*CUTOUT[A-Z_]*).*?frame=\[0,0\]\[\d+,(\d+)\]", dump)
    navigation = re.search(r"type=(?:navigationBars|ITYPE_NAVIGATION_BAR).*?frame=\[0,(\d+)\]\[\d+,(\d+)\]", dump)
    top = max(int(status.group(1)) if status else round(24 * zoom), int(cutout.group(1)) if cutout else 0)
    bottom = int(navigation.group(1)) if navigation and int(navigation.group(2)) == height else height - round(24 * zoom)
    return top, bottom

apk = Path(os.environ.get("WERK_ANDROID_APK", root / "build/werk-android-emulator.apk"))
check_apk(apk)
try:
    adb("install", "-r", str(apk))
    # This is the test emulator and only this package's fixture data is cleared.
    shell("pm", "clear", package)
    shell("run-as", package, "mkdir", "-p", "files/profile")
    adb("shell", f"run-as {package} sh -c 'umask 077; cat > files/profile/settings.txt'",
        input=b"name=Fixture Person\ntheme_mode=1\n")
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(2); alive(); dismiss_other_apps_not_responding(); shot("launch")
    size = shell("wm", "size").strip().split()[-1]
    width, height = map(int, size.split("x"))
    # Werkzeug scales by the screen density, as Android's dp do.
    densities = re.findall(r"density: (\d+)", shell("wm", "density"))
    zoom = int(densities[-1]) / 160
    top, bottom = system_bars(height)
    # The shared Apps screen can change layout; select the visible tool.
    tap_label("Pass"); time.sleep(0.5); alive(); shot("pass")
    runtime_modes = shell("run-as", package, "stat", "-c", "%a", "files/cache", "files/cache/ziran-native").split()
    assert runtime_modes == ["700", "700"], f"Native runtime cache is not private: {runtime_modes}"
    find_label("Site")
    bar = 56
    fill_field("Site", "example.com")
    assert "mInputShown=true" in shell("dumpsys", "input_method"), "Soft keyboard did not open"
    fill_field("Login", "alice")
    fill_field("Master", "test master")
    shot("keyboard")
    hide_keyboard(); alive()
    tap(width // 2, bottom - int(35 * zoom))
    fill_field("Profile", "Android test")
    shell("input", "keyevent", "4"); time.sleep(0.3)
    tap(int(100 * zoom), top + int((105 + bar) * zoom))
    expected = "Android test\texample.com\talice\t16\t1\t1\t1\t1\t1\t\n"
    saved = shell("run-as", package, "cat", "files/apps/pass/profiles.tsv")
    assert saved == expected, f"Profile input/persistence mismatch: {saved!r}"
    assert "test master" not in saved
    print("Android: keyboard input and first saved profile verified", flush=True)
    # Generate from the saved profile and copy it.
    tap(int(100 * zoom), top + int((210 + bar) * zoom))
    # A slow emulator may still be deriving the password.
    time.sleep(2); dismiss_other_apps_not_responding()
    tap(int(100 * zoom), bottom - int(119 * zoom))  # Copy, at the bottom of the scrolled form
    shot("generated")
    tap(width // 2, bottom - int(35 * zoom))
    tap(int(90 * zoom), top + int((55 + bar) * zoom))
    shell("input", "keyevent", "123")  # Move to the end.
    shell("input", "keyevent", *["67" for _ in "Android test"])
    time.sleep(0.5)
    dismiss_other_apps_not_responding()
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
    print("Android: second profile, restart and private permissions verified", flush=True)
    # The shared Profile retains existing names and edits appearance.
    tap_label("Fixture"); time.sleep(0.8); alive()
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "name=Fixture Person\n" in settings, "Profile lost the retained name"
    tap(*scroll_to_label("Dark")); time.sleep(0.5)
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "theme_mode=2\n" in settings and "name=Fixture Person\n" in settings
    shot("profile-appearance")
    print("Android: retained profile name and appearance verified", flush=True)
    tap(*scroll_to_label("Light"))
    # The shared Profile manages nodes on its own page.
    hide_keyboard()
    tap(*scroll_to_label("Nodes", direction="up"))
    tap_label("Add")
    node_input = find_label("address")
    tap(*node_input)
    type_text("https://sync.example.invalid:8443/")
    hide_keyboard()
    # The Add action sits below the visible address field. Its white text
    # and the page heading are unreliable OCR targets on small displays.
    tap(width // 2, node_input[1] + int(64 * zoom))
    settings = shell("run-as", package, "cat", "files/profile/settings.txt")
    assert "https://sync.example.invalid:8443" in settings, "Custom node was not added"
    # The new node is the last row above Add node; its detail page puts
    # Make default below the connection status. Check the saved result.
    _, add_node_y = scroll_to_label("Add")
    tap(width // 2, add_node_y - int(64 * zoom))
    _, status_y = find_label("connected")
    tap(width // 2, status_y + int(64 * zoom))
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
    # These tags report asset loading and native startup without recording the
    # test's typed credentials. The emulator and its profile are disposable.
    logs = adb("logcat", "-d", "-s", "raylib:I", "Werkzeug:I", check=False)
    (output / "startup-logcat.txt").write_bytes(logs.stdout)
    raise
