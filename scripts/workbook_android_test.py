"""Workbook editing and document transfers on an explicitly owned emulator."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
from android_labels import label_position
from android_apk_check import check_apk

root = Path(__file__).resolve().parents[1]
output = root / "build/workbook-android-test"
output.mkdir(parents=True, exist_ok=True)
serial = os.environ.get("WERK_ANDROID_EMULATOR", "")
if not serial and os.environ.get("CI"):
    devices = subprocess.check_output(["adb", "devices"], text=True).splitlines()
    serial = next((line.split()[0] for line in devices if line.startswith("emulator-") and line.split()[-1] == "device"), "")
assert serial.startswith("emulator-"), "Set WERK_ANDROID_EMULATOR to the private test emulator"
package = "xyz.waozi.pass"
apk = Path(os.environ.get("WERK_ANDROID_APK", root / "build/werk-android-emulator.apk"))
check_apk(apk)


def adb(*args, check=True):
    return subprocess.run(["adb", "-s", serial, *map(str, args)], check=check, capture_output=True, timeout=90)


def shell(*args, check=True):
    return adb("shell", *args, check=check).stdout.decode()


def shot(name):
    path = output / (name + ".png")
    path.write_bytes(adb("exec-out", "screencap", "-p").stdout)
    return path


def tap(x, y):
    shell("input", "tap", round(x), round(y))
    time.sleep(.25)


def label(word, scroll=False):
    until = time.monotonic() + 20
    swipes = 0
    while time.monotonic() < until:
        point = label_position(shot("label"), word)
        if point:
            tap(*point)
            return
        if scroll and swipes < 6:
            shell("input", "swipe", width // 2, height * 3 // 4,
                  width // 2, height // 3, "450")
            swipes += 1
            time.sleep(.4)
        time.sleep(.2)
    raise AssertionError("Missing Workbook control: " + word)


def native_label(word):
    until = time.monotonic() + 20
    while time.monotonic() < until:
        path = "/data/local/tmp/werk-window.xml"
        shell("rm", "-f", path, check=False)
        shell("uiautomator", "dump", "--compressed", path, check=False)
        data = shell("cat", path, check=False)
        (output / "system-window.xml").write_text(data)
        try:
            nodes = ET.fromstring(data).iter("node")
        except ET.ParseError:
            nodes = []
        for node in nodes:
            if node.get("text", "").casefold() == word.casefold():
                bounds = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
                if len(bounds) == 4:
                    tap((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
                    return
        point = label_position(shot("system-control"), word)
        if point:
            tap(*point)
            return
        time.sleep(.2)
    raise AssertionError("Missing system document control: " + word)


def document():
    return shell("run-as", package, "cat", "files/apps/workbook/documents/workbook.gnumeric", check=False)


def expect(value, col=0):
    until = time.monotonic() + 20
    while time.monotonic() < until:
        try:
            doc = ET.fromstring(document())
            cells = doc.iter("{http://www.gnumeric.org/v10.dtd}Cell")
            if any(c.get("Row") == "0" and c.get("Col") == str(col) and (c.text or "") == value for c in cells):
                return
        except ET.ParseError:
            pass
        time.sleep(.2)
    raise AssertionError("Workbook did not save fixture " + repr(value))


def hide_keyboard():
    if "mInputShown=true" in shell("dumpsys", "input_method"):
        shell("input", "keyevent", "4")
        time.sleep(.4)


def edit(col, value):
    try:
        previous = next((cell.text or "" for cell in ET.fromstring(document()).iter(
            "{http://www.gnumeric.org/v10.dtd}Cell")
            if cell.get("Row") == "0" and cell.get("Col") == str(col)), "")
    except ET.ParseError:
        previous = ""
    hide_keyboard()
    x, y = (88 + col * 96) * zoom, top + 177 * zoom
    tap(x, y)
    tap(180 * zoom, top + 127 * zoom)
    until = time.monotonic() + 10
    while "mInputShown=true" not in shell("dumpsys", "input_method"):
        if time.monotonic() > until:
            raise AssertionError("Workbook did not focus Android's keyboard")
        time.sleep(.2)
    if "keycombination" in input_commands:
        shell("input", "keycombination", "113", "29")
    else:
        # Older input commands lack Ctrl+A; clear the fixture through its IME.
        shell("input", "keyevent", "123", *["67" for _ in previous])
    shell("input", "text", shlex.quote(value))
    time.sleep(.5)
    hide_keyboard()
    tap(18 * zoom, top + 98 * zoom)
    expect(value, col)


def file_menu():
    hide_keyboard()
    tap(28 * zoom, top + 68 * zoom)


adb("install", "-r", apk)
input_help = adb("shell", "input", check=False)
input_commands = (input_help.stdout + input_help.stderr).decode()
shell("am", "force-stop", package)
shell("run-as", package, "rm", "-rf", "files/apps/workbook", check=False)
shell("rm", "-f", "/sdcard/Download/workbook.gnumeric", check=False)
shell("am", "start", "-n", package + "/android.app.NativeActivity")
time.sleep(1)
width, height = map(int, shell("wm", "size").strip().split()[-1].split("x"))
zoom = max(1, width / 390)
windows = shell("dumpsys", "window")
(output / "window-dump.txt").write_text(windows)
status = re.search(r"type=(?:statusBars|ITYPE_STATUS_BAR).*?frame=\[0,0\]\[\d+,(\d+)\]", windows)
top = int(status.group(1)) if status else round(24 * zoom)
try:
    label("Workbook", scroll=True)
    edit(0, "12")
    edit(1, "=A1*2")
    shot("calculated")
    assert shell("run-as", package, "stat", "-c", "%a", "files/apps/workbook/documents/workbook.gnumeric").strip() == "600"
    shell("am", "force-stop", package)
    shell("am", "start", "-n", package + "/android.app.NativeActivity")
    time.sleep(1)
    label("Workbook", scroll=True)
    expect("12"); expect("=A1*2", 1)
    original = document()
    file_menu(); label("As")
    native_label("Save")
    until = time.monotonic() + 30
    exported = ""
    while time.monotonic() < until:
        exported = shell("cat", "/sdcard/Download/workbook.gnumeric", check=False)
        if exported == original:
            break
        time.sleep(.3)
    assert exported == original, "Android export changed document bytes"
    edit(0, "7")
    file_menu(); label("Open")
    native_label("workbook.gnumeric")
    expect("12"); expect("=A1*2", 1)
    assert shell("cat", "/sdcard/Download/workbook.gnumeric") == exported, "Import modified the selected source"
    file_menu(); label("Open")
    time.sleep(.5)
    shell("input", "keyevent", "4")
    time.sleep(.5)
    expect("12")
    edit(0, "9")
    shot("transferred")
    print("Workbook Android: IME editing, formulas, private save/restart, system document export/import and cancellation passed")
except BaseException:
    shot("failure")
    (output / "document-intents.txt").write_text(shell("dumpsys", "activity", "activities", check=False))
    (output / "crash-log.txt").write_bytes(adb("logcat", "-d", "-b", "crash", check=False).stdout)
    (output / "startup-log.txt").write_bytes(adb("logcat", "-d", "-s", "Werkzeug:I", "art:E", "AndroidRuntime:E", check=False).stdout)
    pid = shell("pidof", package, check=False).strip()
    if pid:
        (output / "application-log.txt").write_bytes(adb("logcat", "-d", "--pid=" + pid, check=False).stdout)
    (output / "ui-task.dex").write_bytes(adb("exec-out", "run-as", package, "cat", "files/ui-task.dex", check=False).stdout)
    (output / "runtime-trace.txt").write_bytes(adb("exec-out", "run-as", package, "cat", "files/runtime-trace.txt", check=False).stdout)
    raise
