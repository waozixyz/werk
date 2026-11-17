#!/usr/bin/env python3
"""Gallery behavioral fixtures and real chooser/UI integration on private Xvfb.

Run via build-queue -- python3 scripts/private-display.py dbus-run-session -- python3
scripts/gallery_gui_test.py. --behavioral-only needs just the native host test;
WERK_GALLERY_TEST_EXECUTABLE selects that test (default build/gallery-test).
"""
import argparse
import contextlib
import csv
import io
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
os.umask(0o077)
parser = argparse.ArgumentParser()
parser.add_argument("--behavioral-only", action="store_true")
args = parser.parse_args()
work = ROOT / "build/gallery-test-fixtures"
if work.exists():
    shutil.rmtree(work)
work.mkdir(parents=True)
photos = work / "photos"
photos.mkdir()
(photos / "Album").mkdir()
empty = work / "empty"
empty.mkdir()
outside = work / "photos-other"
outside.mkdir()
# Generated fixtures only. No personal photo or desktop access.
for name, color in (("a.png", "red"), ("z.JPG", "blue"), ("Album/b.png", "green"), ("été.png", "cyan")):
    image = Image.new("RGB", (640, 480), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((220, 100, 420, 380), fill="yellow")
    image.save(photos / name)
Image.new("RGB", (40, 40), "magenta").save(outside / "outside.png")
# Valid dimensions with a corrupt payload exercises the real host decoder.
(photos / "broken.png").write_bytes((photos / "a.png").read_bytes()[:33] + b"corrupt image fixture")
(photos / "notes.txt").write_text("not a photo")
(photos / ".hidden.png").write_bytes((photos / "a.png").read_bytes())
(photos / "escaped.png").symlink_to(outside / "outside.png")
(photos / "EscapedAlbum").symlink_to(outside, target_is_directory=True)
large = work / "large"
large.mkdir()
for index in reversed(range(520)):
    (large / f"{index:04}.png").write_bytes((photos / "a.png").read_bytes())
images = work / "image-cases"
images.mkdir()
# An ordinary six-megapixel PNG exceeds the former16MiB cutoff without
# requiring a large decoder allocation. All assets stay binary on disk.
Image.new("RGB", (3072, 2048), "red").save(images / "00-large.png", compress_level=0)
assert (images / "00-large.png").stat().st_size > 16 * 1024 * 1024
with (images / "01-size-limit.png").open("wb") as stream:
    stream.write((photos / "a.png").read_bytes()[:33])
    stream.truncate(64 * 1024 * 1024 + 1)
header = bytearray((photos / "a.png").read_bytes()[:33])
header[16:24] = struct.pack(">II", 40000, 40000)
(images / "02-pixel-limit.png").write_bytes(header)
(images / "03-invalid.png").write_bytes(b"not an image")
for index, suffix in enumerate(("bmp", "webp", "gif", "jpg"), 4):
    Image.new("RGB", (80, 60), "blue").save(images / f"{index:02}-photo.{suffix}")
retry = work / "retry"
retry.mkdir()
(retry / "retry.png").write_bytes((photos / "a.png").read_bytes())
blocked = work / "blocked"
blocked.write_text("a regular file cannot contain location.txt")
missing_programs = work / "no-programs"
missing_programs.mkdir()
env = dict(os.environ)
for name, sub in (("HOME", "home"), ("WERK_DATA", "data"), ("ENTITY_DATA", "entity"),
                  ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "share"), ("XDG_CACHE_HOME", "cache")):
    env[name] = str(work / sub)
    Path(env[name]).mkdir(parents=True, exist_ok=True)
env["WERK_ASSETS"] = os.environ.get("WERK_TEST_ASSETS", str(ROOT / "build"))
env["WERK_GALLERY_TEST_DATA"] = str(work / "host-data")
env["WERK_GALLERY_TEST_OUTSIDE"] = str(outside / "outside.png")
env["WERK_GALLERY_TEST_CANDIDATE"] = str(outside)
env["WERK_GALLERY_TEST_BLOCKED"] = str(blocked)
private = Path(env["WERK_GALLERY_TEST_DATA"]) / "gallery"
private.mkdir(parents=True, mode=0o700)
exe = Path(os.environ.get("WERK_GALLERY_TEST_EXECUTABLE", ROOT / "build/gallery-test"))
assert exe.is_file(), f"Build fixture host test first: {exe}"
for mode, location in (("normal", photos), ("persist", photos), ("images", images), ("retry", retry), ("chooser-missing", photos), ("empty", empty), ("large", large), ("revoked", work / "missing"), ("first-save-failure", None)):
    if location is None:
        (private / "location.txt").unlink(missing_ok=True)
    else:
        (private / "location.txt").write_text(str(location))
        (private / "location.txt").chmod(0o600)
    native_env = {key: value for key, value in env.items() if key not in
                  ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER")}
    native_env["WERK_GALLERY_TEST_MODE"] = mode
    if mode == "chooser-missing":
        native_env["PATH"] = str(missing_programs)
    result = subprocess.run([str(exe)], env=native_env, timeout=30)
    assert result.returncode == 0, f"Gallery native fixture {mode}: exit {result.returncode}"
    if mode in ("normal", "persist"):
        assert (private / "location.txt").read_text() == str(outside if mode == "persist" else photos)
        assert (private / "location.txt").stat().st_mode & 0o777 == 0o600
    if mode == "persist":
        # A fresh OS process must read the actual grant just saved by the
        # native service. Do not preseed or rewrite location.txt here.
        reopened = subprocess.run([str(exe)], env=dict(native_env, WERK_GALLERY_TEST_MODE="persist-reopen"), timeout=30)
        assert reopened.returncode == 0, "Saved grant did not survive a fresh process"
print("Gallery native fixtures passed: sorting/albums, real grant save/reload, failed-save rollback, retry after read failure, >16MiB image, byte/pixel bounds, format headers, empty/missing roots, symlink isolation and viewer state", flush=True)
if args.behavioral_only:
    raise SystemExit(0)
assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Use scripts/private-display.py"
# First launch has no grant: exercise empty, real chooser cancellation and
# successful folder grant, viewer controls and process restart persistence.
binary = Path(os.environ.get("WERK_TEST_BINARY", ROOT / "build/werk"))
app = None
window = None

def command(*values):
    return subprocess.check_output(values, env=env, text=True, timeout=20).strip()

def wait_until(action, description, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert app.poll() is None, "Gallery host exited"
        value = action()
        if value:
            return value
        time.sleep(.15)
    capture("failure")
    raise AssertionError(description)

def capture(name):
    path = work / f"{name}.png"
    command("import", "-window", window, str(path))
    return path

def words(region="all", psm=11):
    path = capture("current")
    with Image.open(path) as image:
        top = max(0, image.height - 128) if region == "footer" else 0
        bottom = min(152, image.height) if region == "header" else image.height
        image = image.crop((0, top, image.width, bottom))
        image.convert("RGB").resize((image.width * 3, image.height * 3)).save(work / "text.png")
    text = command("tesseract", str(work / "text.png"), "stdout", "--psm", str(psm), "-c", "tessedit_create_tsv=1")
    rows = [row for row in csv.DictReader(io.StringIO(text), delimiter="\t")
            if (row.get("text") or "").strip() and (row.get("left") or "").isdigit()]
    for row in rows:
        row["top"] = str(int(row["top"]) + top * 3)
    return rows

def has_text(expected):
    return any(expected.lower() in " ".join(row["text"] for row in words(region, psm)).lower()
               for region, psm in (("all", 11), ("header", 6), ("footer", 6)))

def click_text(expected):
    def find():
        parts = expected.split()
        # Bright fixture photos can dominate sparse OCR. Read the viewer's
        # control strip separately while keeping exact labels and coordinates.
        for region, psm in (("all", 11), ("header", 6), ("footer", 6)):
            rows = words(region, psm)
            for index, row in enumerate(rows):
                if [item["text"].strip().lower() for item in rows[index:index + len(parts)]] == [p.lower() for p in parts]:
                    return (int(row["left"]) + int(row["width"]) // 2) // 3, (int(row["top"]) + int(row["height"]) // 2) // 3
        return None
    x, y = wait_until(find, "Missing Gallery control: " + expected)
    command("xdotool", "windowfocus", "--sync", window)
    command("xdotool", "mousemove", "--window", window, str(x), str(y))
    command("xdotool", "click", "1")
    time.sleep(.3)
    print(f"Gallery clicked {expected!r} at {x},{y}", flush=True)

def launch():
    global app, window
    with (work / "runtime.log").open("ab") as log:
        app = subprocess.Popen([str(binary)], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    def find():
        result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)], env=env, text=True, capture_output=True)
        return result.stdout.splitlines()[0] if result.returncode == 0 else None
    window = wait_until(find, "Werkzeug did not open its test window")
    command("xdotool", "windowfocus", "--sync", window)
    click_text("Gallery")

def chooser():
    def find():
        result = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Choose a local photo folder$"], env=env, text=True, capture_output=True)
        if result.returncode:
            return None
        for candidate in result.stdout.splitlines():
            # GTK may delegate Zenity's chooser to the portal on our private
            # session bus. Its window then belongs to the portal process.
            # The exact title is confined to this test's private Xvfb; also
            # require the host's actual chooser process to remain alive.
            children = subprocess.run(["ps", "-o", "comm=", "--ppid", str(app.pid)],
                                      env=env, text=True, capture_output=True)
            if "zenity" in children.stdout.split():
                return candidate
        return None
    try:
        return wait_until(find, "Native folder chooser did not appear")
    except AssertionError:
        # Only this test's Xvfb windows are visible through env[DISPLAY].
        windows = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "."],
                                 env=env, text=True, capture_output=True)
        for candidate in windows.stdout.splitlines()[:20]:
            title = command("xdotool", "getwindowname", candidate)
            pid = subprocess.run(["xdotool", "getwindowpid", candidate], env=env, text=True, capture_output=True)
            print(f"Private chooser diagnostic: {candidate} pid={pid.stdout.strip()} title={title!r}", flush=True)
        children = subprocess.run(["ps", "-o", "pid,ppid,comm,wchan:32", "--ppid", str(app.pid)],
                                  env=env, text=True, capture_output=True)
        print(children.stdout, flush=True)
        raise

def colors(path):
    with Image.open(path) as image:
        return sum(1 for r, g, b in image.convert("RGB").getdata() if r > 190 and g < 70 and b < 70), sum(1 for r, g, b in image.convert("RGB").getdata() if b > 190 and r < 70 and g < 70)

def marker_area(path):
    with Image.open(path) as image:
        return sum(1 for r, g, b in image.convert("RGB").getdata() if r > 190 and g > 190 and b < 70)

def marker_center(path):
    with Image.open(path) as image:
        total_x = total_y = count = 0
        for index, (r, g, b) in enumerate(image.convert("RGB").getdata()):
            if r > 190 and g > 190 and b < 70:
                total_x += index % image.width
                total_y += index // image.width
                count += 1
        assert count, "Fixture marker is not visible"
        return total_x / count, total_y / count

def assert_photo_fits(path):
    with Image.open(path) as image:
        left, top, right, bottom = image.width, image.height, 0, 0
        for index, (r, g, b) in enumerate(image.convert("RGB").getdata()):
            if r > 190 and g < 70 and b < 70:
                x, y = index % image.width, index // image.width
                left, top, right, bottom = min(left, x), min(top, y), max(right, x), max(bottom, y)
        assert right > left and bottom > top, "Photo is absent"
        assert left >= 8 and right < image.width - 8 and top > 80 and bottom < image.height - 90, "Fit escaped the viewer viewport"

def choose_location(location):
    click_text("Choose folder")
    dialog = chooser()
    def dialog_key(key):
        command("xdotool", "windowfocus", "--sync", dialog)
        command("xdotool", "key", "--clearmodifiers", key)
    # Leave GTK's Recent search view before entering a directory.
    dialog_key("alt+Home")
    time.sleep(.5)
    dialog_key("ctrl+l")
    command("xdotool", "type", "--clearmodifiers", str(location) + "/")
    time.sleep(.5)
    dialog_key("Return")
    def closed():
        visible = subprocess.run(["xdotool", "search", "--onlyvisible", "--name",
                                  "^Choose a local photo folder$"], env=env, text=True,
                                 capture_output=True)
        return dialog not in visible.stdout.splitlines()
    try:
        wait_until(closed, "Native folder chooser did not accept the fixture folder")
    except AssertionError:
        focus = command("xdotool", "getwindowfocus")
        print(f"Chooser focus: {focus} {command('xdotool', 'getwindowname', focus)!r}", flush=True)
        command("import", "-window", dialog, str(work / "chooser-selection.png"))
        raise

try:
    launch()
    assert has_text("Choose a folder"), "Missing initial empty state"
    click_text("Choose folder")
    dialog = chooser()
    command("xdotool", "windowfocus", "--sync", dialog)
    command("xdotool", "key", "Escape")
    wait_until(lambda: has_text("cancelled"), "Chooser cancellation was not shown")
    choose_location(photos)
    wait_until(lambda: has_text("a.png") and has_text("z.JPG"), "Fixture photos did not populate")
    grid = capture("grid")
    red, blue = colors(grid)
    assert red > 2000 and blue > 2000, "Real fixture thumbnails were not rendered"
    saved = Path(env["WERK_DATA"]) / "gallery/location.txt"
    blocked_save = saved.with_name("location.txt.new")
    blocked_save.mkdir()
    choose_location(empty)
    wait_until(lambda: has_text("Could not save") and has_text("a.png"), "Failed save did not preserve the previous album")
    assert saved.read_text() == str(photos), "Failed selection replaced the saved grant"
    blocked_save.rmdir()
    choose_location(empty)
    wait_until(lambda: has_text("No supported photos"), "Folder selection did not recover after save failure")
    choose_location(photos)
    wait_until(lambda: has_text("a.png") and has_text("z.JPG"), "Original fixture folder did not reopen")
    click_text("Album")
    wait_until(lambda: has_text("b.png"), "Album did not open")
    click_text("Up")
    click_text("a.png")
    wait_until(lambda: has_text("Zoom in"), "Viewer did not open")
    # The centered yellow fixture marker grows when zoomed; the surrounding
    # red region can shrink because zoom correctly clips the photo's edges.
    before = marker_area(capture("fit"))
    click_text("Zoom in")
    after = marker_area(capture("zoom"))
    assert after > before * 1.1, "Zoom did not change rendered photo scale"
    center = marker_center(capture("before-pan"))
    click_text("Pan right")
    moved = marker_center(capture("pan-right"))
    assert moved[0] < center[0] - 10, "Horizontal pan did not move the image"
    click_text("Pan down")
    lowered = marker_center(capture("pan-down"))
    assert lowered[1] < moved[1] - 10, "Vertical pan did not move the image"
    click_text("Fit")
    fitted = marker_area(capture("fit-restored"))
    assert abs(fitted - before) < before * .12, "Fit did not restore rendered scale"
    click_text("Next")
    wait_until(lambda: has_text("Cannot decode image") and has_text("Retry image"), "Corrupt image lacks a recoverable decoder error")
    click_text("Retry image")
    wait_until(lambda: has_text("Cannot decode image"), "Corrupt-image retry lost its error state")
    capture("unavailable-image")
    removed = (photos / "z.JPG").read_bytes()
    (photos / "z.JPG").unlink()
    click_text("Next")
    wait_until(lambda: has_text("Cannot read image") and has_text("Retry image"), "Unreadable image lacks a recoverable read error")
    (photos / "z.JPG").write_bytes(removed)
    click_text("Retry image")
    wait_until(lambda: colors(capture("next"))[1] > 5000, "Next photo did not render")
    click_text("Previous")
    click_text("Previous")
    wait_until(lambda: colors(capture("previous"))[0] > 5000, "Previous photo did not render")
    app.terminate()
    app.wait(timeout=10)
    launch()
    wait_until(lambda: has_text("a.png"), "Selected location did not survive restart")
    command("xdotool", "windowsize", "--sync", window, "360", "640")
    wait_until(lambda: has_text("Choose folder"), "Narrow Gallery controls did not render")
    click_text("a.png")
    wait_until(lambda: colors(capture("narrow-viewer"))[0] > 3000 and has_text("Fit") and has_text("Next"), "Narrow viewer or controls did not render")
    narrow_before = marker_area(capture("narrow-fit"))
    click_text("Zoom in")
    assert marker_area(capture("narrow-zoom")) > narrow_before * 1.1, "Narrow zoom did not scale image"
    click_text("Fit")
    assert abs(marker_area(capture("narrow-restored")) - narrow_before) < narrow_before * .12, "Narrow Fit did not restore scale"
    assert_photo_fits(capture("narrow-fitted-bounds"))
    command("xdotool", "windowsize", "--sync", window, "520", "700")
    wait_until(lambda: colors(capture("resized-viewer"))[0] > 3000 and has_text("Fit"), "Resized viewer lost image or controls")
    assert_photo_fits(capture("resized-fitted-bounds"))
    click_text("Albums")
    saved = Path(env["WERK_DATA"]) / "gallery/location.txt"
    assert saved.read_text() == str(photos)
    assert saved.stat().st_mode & 0o777 == 0o600
    assert saved.parent.stat().st_mode & 0o777 == 0o700
    command("xdotool", "windowsize", "--sync", window, "960", "720")
    choose_location(images)
    wait_until(lambda: has_text("00-large.png"), "Large-image fixture did not populate")
    click_text("00-large.png")
    wait_until(lambda: colors(capture("large-photo"))[0] > 5000, "Ordinary photo over16MiB did not render")
    # Next/Previous buttons were exercised above. Also cover the viewer's
    # keyboard navigation while advancing through large-image error cases.
    command("xdotool", "key", "--window", window, "Right")
    wait_until(lambda: has_text("Image exceeds") and has_text("Retry image"), "Byte limit lacks an explicit image error")
    command("xdotool", "key", "--window", window, "Right")
    wait_until(lambda: has_text("Image exceeds") and has_text("Retry image"), "Pixel limit lacks an explicit image error")
    print("Gallery private-Xvfb GUI passed: actual chooser/cancel, thumbnails/albums, decoder/read errors and retry, large image and limits, next/previous, rendered fit/zoom/pan, persisted root, narrow viewer", flush=True)
finally:
    if app:
        # The host and its native chooser have their own test-only process
        # group. Also clean up a chooser left open by a failing assertion.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(app.pid, signal.SIGTERM)
        try:
            app.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(app.pid, signal.SIGKILL)
            app.wait(timeout=10)
