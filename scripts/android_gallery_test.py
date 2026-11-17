#!/usr/bin/env python3
"""Exercise the real local folder grant and viewer on a private emulator."""
import os
from pathlib import Path
import re
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw
from android_labels import label_position
from android_startup import launch_home
from android_apk_check import check_apk

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/android-gallery-test"
OUT.mkdir(parents=True, exist_ok=True)
SERIAL = os.environ.get("WERK_ANDROID_EMULATOR", "")
assert SERIAL.startswith("emulator-"), "Select an explicitly owned private emulator"
PACKAGE = "xyz.waozi.pass"
FOLDER = "/sdcard/Pictures/WerkGalleryFixture"


def adb(*args, check=True, input=None):
    return subprocess.run(["adb", "-s", SERIAL, *args], check=check,
                          capture_output=True, input=input, timeout=90)


def shell(*args, check=True):
    return adb("shell", *args, check=check).stdout.decode()


def frame(name="current"):
    path = OUT / (name + ".png")
    path.write_bytes(adb("exec-out", "screencap", "-p").stdout)
    return path


def tap(x, y):
    shell("input", "tap", str(x), str(y))
    time.sleep(.4)


def label(word, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        path = frame()
        position = label_position(path, word)
        if position:
            return position
        time.sleep(.3)
    raise AssertionError("Missing Gallery label: " + word)


def expect_text(expected):
    wanted = "".join(character.casefold() for character in expected if character.isalnum())
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        text = subprocess.check_output(["tesseract", str(frame()), "stdout", "--psm", "11"],
                                       stderr=subprocess.DEVNULL, text=True)
        actual = "".join(character.casefold() for character in text if character.isalnum())
        if wanted in actual:
            return
        time.sleep(.3)
    raise AssertionError("Missing visible Gallery text: " + expected)


def click(word):
    tap(*label(word))


def system_nodes():
    path = "/data/local/tmp/werk-gallery-ui.xml"
    shell("uiautomator", "dump", "--compressed", path)
    text = shell("cat", path)
    (OUT / "picker.xml").write_text(text)
    return list(ET.fromstring(text).iter("node"))


def system_click(*labels, required=True):
    for node in system_nodes():
        if node.get("text", "").casefold() in [s.casefold() for s in labels] or node.get("content-desc", "").casefold() in [s.casefold() for s in labels]:
            bounds = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
            if len(bounds) == 4 and node.get("enabled") != "false":
                tap((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
                return True
    if required:
        raise AssertionError("Missing system picker control: " + repr(labels))
    return False


def picker_ready():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if any(node.get("text", "").casefold() == "use this folder"
                   for node in system_nodes()):
                return
        except (subprocess.SubprocessError, ET.ParseError):
            pass
        time.sleep(.3)
    raise AssertionError("System folder picker did not become ready")


def cancel_picker():
    picker_ready()
    # Back first navigates a remembered folder's parents. Stop as soon as
    # DocumentsUI returns to our activity; never send Back into Gallery.
    for _ in range(12):
        shell("input", "keyevent", "4")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            activities = shell("dumpsys", "activity", "activities")
            resumed = [line for line in activities.splitlines() if "mResumedActivity" in line]
            if any(PACKAGE + "/android.app.NativeActivity" in line for line in resumed):
                return
            time.sleep(.2)
    raise AssertionError("System folder picker did not cancel back to Gallery")


def choose(folder):
    click("Choose")
    picker_ready()
    # DocumentsUI may restore the last selected folder. Select the local
    # device root explicitly rather than relying on a provider's history.
    if system_click("Show roots", "Open navigation drawer", required=False):
        if not system_click("Internal storage", "Pixel 2", "Android SDK built for x86_64", required=False):
            nodes = system_nodes()
            candidates = [node for node in nodes if node.get("resource-id", "").endswith("/title") and
                          ("sdk_" in node.get("text", "").lower() or "emulator" in node.get("text", "").lower())]
            assert candidates, "Local device root missing from system picker"
            bounds = list(map(int, re.findall(r"\d+", candidates[0].get("bounds", ""))))
            tap((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
    else:
        # Some DocumentsUI tree pickers expose only breadcrumbs. The first
        # breadcrumb must identify this local device, then returns to its root.
        crumbs = [node for node in system_nodes()
                  if node.get("resource-id", "").endswith("/breadcrumb_text")]
        assert crumbs, "Local folder picker has neither roots nor breadcrumbs"
        name = crumbs[0].get("text", "").casefold()
        assert "sdk_" in name or "emulator" in name or name in ("internal storage", "pixel 2"), name
        bounds = list(map(int, re.findall(r"\d+", crumbs[0].get("bounds", ""))))
        tap((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
    system_click("Pictures")
    system_click(folder)
    system_click("Use this folder")
    system_click("Allow")
    time.sleep(1)


def pixels(name, color):
    with Image.open(frame(name)) as image:
        data = image.convert("RGB").getdata()
        if color == "red":
            return sum(r > 190 and g < 70 and b < 70 for r, g, b in data)
        if color == "blue":
            return sum(b > 190 and r < 70 and g < 70 for r, g, b in data)
        if color == "green":
            return sum(g > 90 and r < 70 and b < 70 for r, g, b in data)
        return sum(r > 190 and g > 190 and b < 70 for r, g, b in data)


apk = Path(os.environ.get("WERK_ANDROID_APK", ROOT / "build/werk-android-emulator.apk"))
check_apk(apk)
adb("install", "-r", str(apk))
fixtures = OUT / "photos"
(fixtures / "Album").mkdir(parents=True, exist_ok=True)
for name, color in (("a.png", "red"), ("z.JPG", "blue"), ("Album/b.png", "green")):
    image = Image.new("RGB", (640, 480), color)
    ImageDraw.Draw(image).rectangle((220, 100, 420, 380), fill="yellow")
    image.save(fixtures / name)
(fixtures / "broken.png").write_bytes((fixtures / "a.png").read_bytes()[:33] + b"corrupt image fixture")
image_cases = fixtures / "ImageCases"
image_cases.mkdir(exist_ok=True)
Image.new("RGB", (3072, 2048), "red").save(image_cases / "00-large.png", compress_level=0)
assert (image_cases / "00-large.png").stat().st_size > 16 * 1024 * 1024
with (image_cases / "01-byte-limit.png").open("wb") as stream:
    stream.write((fixtures / "a.png").read_bytes()[:33])
    stream.truncate(64 * 1024 * 1024 + 1)
header = bytearray((fixtures / "a.png").read_bytes()[:33])
header[16:24] = struct.pack(">II", 40000, 40000)
(image_cases / "02-pixel-limit.png").write_bytes(header)
rotated = Image.new("RGB", (640, 480), "blue")
ImageDraw.Draw(rotated).rectangle((0, 0, 639, 239), fill="red")
metadata = Image.Exif()
metadata[274] = 6  # EXIF: rotate clockwise, making red the right half.
rotated.save(image_cases / "03-rotated.jpg", quality=95, exif=metadata)
shell("mkdir", "-p", FOLDER, "/sdcard/Pictures/WerkGalleryEmpty")
adb("push", str(fixtures) + "/.", FOLDER + "/")
# Only fixture state in this private test package is replaced.
shell("am", "force-stop", PACKAGE)
shell("run-as", PACKAGE, "rm", "-rf", "files/gallery")
launch_home(adb, OUT, PACKAGE, "gallery-launch")
click("Gallery")
label("Choose")
click("Choose")
cancel_picker()
label("cancelled")
choose("WerkGalleryFixture")
label("WerkGalleryFixture")
label("Album")
assert pixels("red-thumbnail", "red") > 500, "Local PNG thumbnail was not rendered"
assert pixels("blue-thumbnail", "blue") > 500, "Local JPEG thumbnail was not rendered"
click("a.png")
assert pixels("red-viewer", "red") > 5000, "Selected local image was not rendered"
yellow = pixels("fit-marker", "yellow")
click("in")
zoomed = pixels("zoom-marker", "yellow")
assert zoomed > yellow * 1.3, "Zoom did not enlarge the rendered image"
click("Pan left")
assert pixels("pan-marker", "yellow") < zoomed * .9, "Pan did not move the enlarged image"
click("Fit")
assert abs(pixels("fit-restored", "yellow") - yellow) < yellow * .05, "Fit did not restore the image viewport"
click("Next")  # broken fixture: navigation must continue past unreadable data.
label("broken.png")
label("decode")
adb("push", str(fixtures / "a.png"), FOLDER + "/broken.png")
click("Retry image")
assert pixels("retry-image", "red") > 5000, "Retry did not reopen the repaired image"
click("Next")
assert pixels("blue-viewer", "blue") > 5000
click("Previous")
label("broken.png")
click("Albums")
click("Album")
expect_text("WerkGalleryFixture / Album")
click("b.png")
assert pixels("album-viewer", "green") > 5000
click("Albums")
click("Up")
click("ImageCases")
expect_text("WerkGalleryFixture / ImageCases")
click("00-large.png")
assert pixels("large-image", "red") > 5000, "An ordinary photo larger than 16 MiB did not render"
click("Next")
label("exceeds")
click("Next")
label("exceeds")
click("Next")
label("03-rotated.jpg")
with Image.open(frame("exif-rotation")) as image:
    red_x = red_count = blue_x = blue_count = 0
    for index, (r, g, b) in enumerate(image.convert("RGB").getdata()):
        if r > 190 and g < 70 and b < 70:
            red_x += index % image.width
            red_count += 1
        if b > 190 and r < 70 and g < 70:
            blue_x += index % image.width
            blue_count += 1
    assert red_count > 5000 and blue_count > 5000
    assert red_x / red_count > blue_x / blue_count + 100, "JPEG EXIF orientation was not applied"
click("Albums")
click("Up")
location = shell("run-as", PACKAGE, "cat", "files/gallery/location.txt").strip()
assert location.startswith("content://com.android.externalstorage.documents/tree/"), location
assert shell("run-as", PACKAGE, "stat", "-c", "%a", "files/gallery", "files/gallery/location.txt").split() == ["700", "600"]
shell("am", "force-stop", PACKAGE)
launch_home(adb, OUT, PACKAGE, "gallery-restart")
click("Gallery")
label("Album")
click("a.png")
assert pixels("persisted-grant", "red") > 5000, "Persisted folder grant did not survive restart"
click("Albums")
choose("WerkGalleryEmpty")
label("supported")
choose("WerkGalleryFixture")
shell("mv", FOLDER, FOLDER + "-removed")
click("Refresh")
label("Cannot")
frame("revoked-folder")
assert shell("pidof", PACKAGE).strip(), "Gallery failure killed its host"
print("Android Gallery: real local picker, cancel, album breadcrumbs, rendered images, zoom/pan/Fit, decoder failure/retry, large photo and size limits, private persisted grant, restart, empty and revoked folders passed", flush=True)
