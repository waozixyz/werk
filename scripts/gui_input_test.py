#!/usr/bin/env python3
"""Exercise the real desktop app and clipboard on the harness's private Xvfb."""
from pathlib import Path
import ctypes
import hashlib
import os
import subprocess
import tempfile
import time

assert os.environ.get("PASS_TEST_PRIVATE_DISPLAY") == "1", "Run scripts/gui_input_test.sh"
root = Path(__file__).resolve().parents[1]
output = root / "build/gui-input"
output.mkdir(parents=True, exist_ok=True)
fixture_context = tempfile.TemporaryDirectory(prefix="profile-", dir=output)
fixture = Path(fixture_context.name)
environment = dict(os.environ)
private_display = environment.pop("DISPLAY")
environment.pop("WAYLAND_DISPLAY", None)
environment["DISPLAY"] = private_display
app = None
window = None

# Observe the actual OS cursor on this harness's private display.
class CursorImage(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short),
                ("width", ctypes.c_ushort), ("height", ctypes.c_ushort),
                ("xhot", ctypes.c_ushort), ("yhot", ctypes.c_ushort),
                ("serial", ctypes.c_ulong), ("pixels", ctypes.POINTER(ctypes.c_ulong))]

xlib = ctypes.CDLL("libX11.so.6")
xfixes = ctypes.CDLL("libXfixes.so.3")
xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
xlib.XOpenDisplay.restype = ctypes.c_void_p
xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
xlib.XFree.argtypes = [ctypes.c_void_p]
xfixes.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
xfixes.XFixesGetCursorImage.restype = ctypes.POINTER(CursorImage)
cursor_display = xlib.XOpenDisplay(private_display.encode())
assert cursor_display, "Could not open the harness's private cursor display"

def cursor_at(x, y):
    command("xdotool", "mousemove", "--window", window, str(x), str(y))
    time.sleep(0.2)
    captured = xfixes.XFixesGetCursorImage(cursor_display)
    assert captured, "Could not read the private display cursor"
    try:
        data = captured.contents
        pixels = bytes().join(int(data.pixels[i]).to_bytes(8, "little")
                              for i in range(data.width * data.height))
        return data.width, data.height, data.xhot, data.yhot, hashlib.sha256(pixels).digest()
    finally:
        xlib.XFree(captured)

def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=10)

def start():
    global app, window
    window = None
    app = subprocess.Popen([str(root / "build/pass-gui")], cwd=fixture, env=environment)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert app.poll() is None, "Pass exited before showing its window"
        result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                                env=environment, capture_output=True, text=True)
        if result.returncode == 0:
            window = result.stdout.splitlines()[0]
            command("xdotool", "windowfocus", "--sync", window)
            time.sleep(0.3)
            return
        time.sleep(0.1)
    owned = subprocess.run(["xdotool", "search", "--pid", str(app.pid)],
                           env=environment, capture_output=True, text=True)
    wait = Path(f"/proc/{app.pid}/wchan").read_text().strip()
    raise AssertionError(f"Pass did not show its window: pid={app.pid}, owned={owned.stdout!r}, wait={wait}")

def stop():
    if app and app.poll() is None:
        app.terminate()
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
            app.wait()

def click(x, y):
    command("xdotool", "mousemove", "--window", window, str(x), str(y), "click", "1")
    time.sleep(0.2)

def type_text(value):
    command("xdotool", "type", "--window", window, "--delay", "30", value)
    time.sleep(0.2)

def dimensions():
    values = dict(line.split("=", 1) for line in command("xdotool", "getwindowgeometry", "--shell", window).splitlines())
    return int(values["WIDTH"]), int(values["HEIGHT"])

def form_bounds():
    width, height = dimensions()
    panel = min(width - 36, 480)
    left = (width - panel) / 2
    scrollbar = 10 if height - 110 < 648 else 0
    return left, panel, left + panel - 10 - scrollbar, height

try:
    start()
    assert dimensions() == (420, 760), "Pass did not open at its compact desktop size"
    left, panel, right, height = form_bounds()
    arrow = cursor_at(410, 520)
    hand = cursor_at(round(left + panel / 6), height - 35)
    text_cursor = cursor_at(round(left + 72), 55)
    assert hand != arrow and text_cursor not in (arrow, hand), "Buttons and fields did not select hand/text cursors"
    assert cursor_at(round(right - 137), 259) == hand, "Length decrement did not use the standard button cursor"
    assert cursor_at(round(right - 14), 259) == hand, "Length increment did not use the standard button cursor"
    assert cursor_at(round(right - 75), 259) == arrow, "Numeric display incorrectly advertised text editing"
    assert cursor_at(round(right - 137), 309) not in (arrow, hand, text_cursor), "Counter minimum did not disable decrement"
    assert cursor_at(410, 520) == arrow, "Cursor did not reset when leaving controls"
    command("xdotool", "windowsize", "--sync", window, "960", "600")
    time.sleep(0.3)
    assert dimensions() == (960, 600)
    left, panel, right, height = form_bounds()
    assert cursor_at(round(left - 20), 55) == arrow, "Wide-window inputs exceeded the centered maximum width"
    assert cursor_at(round(left + 72), 55) == text_cursor, "Centered fields stopped accepting text after resizing"
    assert cursor_at(round(right + 20), 55) == arrow, "Wide-window inputs exceeded their right boundary"
    command("import", "-window", window, str(output / "pass-wide.png"))
    # The integrated buttons still step once and preserve generation settings.
    click(round(right - 14), 259)
    click(round(right - 137), 259)
    click(round(left + 72), 55); type_text("example.com")
    click(round(left + 72), 130); type_text("alice")
    click(round(left + 72), 205); type_text("test master")
    command("xdotool", "mousemove", "--window", window, str(round(left + 102)), "400",
            "click", "--repeat", "20", "--delay", "40", "5")
    time.sleep(0.3)
    overflow = max(0, 682 - (height - 110))
    click(round(left + 102), 535 - overflow)  # Generate after the visible fingerprint row.
    click(round(left + 102), 690 - overflow)  # Copy the generated password.
    # Independently derived by scripts/lesspass_compat_test.py.
    expected = "dEeEDu7/b27L#r<&"
    actual = command("xclip", "-selection", "clipboard", "-out")
    assert actual == expected, f"Desktop generation/copy mismatch: {actual!r}"
    click(480, 565)
    click(round(left + 72), 55); type_text("Desktop test")
    click(round(left + 102), 105)
    saved = "Desktop test\texample.com\talice\t16\t1\t1\t1\t1\t1\t\n"
    profiles = fixture / "profiles.tsv"
    assert profiles.read_text() == saved
    assert "test master" not in profiles.read_text()
    stop(); start()
    left, panel, right, height = form_bounds()
    click(210, height - 35)
    click(round(right - 50), 216)  # Delete a profile loaded from disk after restart.
    assert profiles.read_text() == "", "Reloaded profile could not be deleted"
    print("Ziran desktop: compact default window, capped centered wide layout, native cursors, number steps, typing, expected password, clipboard, profiles, restart and deletion pass")
except BaseException:
    if app and app.poll() is None and window:
        subprocess.run(["xwd", "-silent", "-id", window, "-out", str(output / "failure.xwd")],
                       env=environment, timeout=5, check=False)
    raise
finally:
    stop()
    fixture_context.cleanup()
    xlib.XCloseDisplay(cursor_display)
