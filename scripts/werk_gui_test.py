#!/usr/bin/env python3
"""Drive Werk and its four apps on the harness's private Xvfb display.

Uses disposable data and cache folders and fixture secrets only. Run
through scripts/werk_gui_test.sh, which starts the private display.
"""
from pathlib import Path
import base64
import hashlib
import hmac
import os
import shutil
import struct
import subprocess
import time

assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Run scripts/werk_gui_test.sh"
root = Path(__file__).resolve().parents[1]
output = root / "build/werk-gui-test"
shutil.rmtree(output, ignore_errors=True)
data = output / "data"
cache = output / "cache"
data.mkdir(parents=True)
cache.mkdir(parents=True)
environment = dict(os.environ)
environment.pop("WAYLAND_DISPLAY", None)
environment["WERK_DATA"] = str(data)
environment["XDG_CACHE_HOME"] = str(cache)
environment["WERK_ASSETS"] = str(root / "build")
app = None
window = None

# The RFC 6238 SHA-1 fixture key, never a real account.
FIXTURE_SECRET = base64.b32encode(b"12345678901234567890").decode()
FIXTURE_LINK = f"otpauth://totp/Fixture:alice@example.com?secret={FIXTURE_SECRET}&issuer=Fixture"


def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=20)


def start():
    global app, window
    app = subprocess.Popen([str(root / "build/werk")], env=environment)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert app.poll() is None, "Werk exited before showing its window"
        found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                               env=environment, capture_output=True, text=True)
        if found.returncode == 0:
            window = found.stdout.splitlines()[0]
            command("xdotool", "windowfocus", "--sync", window)
            time.sleep(0.5)
            return
        time.sleep(0.1)
    raise AssertionError("Werk did not show its window")


def stop():
    if app and app.poll() is None:
        app.terminate()
        app.wait(timeout=10)


def click(x, y):
    command("xdotool", "mousemove", "--window", window, str(x), str(y))
    time.sleep(0.1)
    command("xdotool", "click", "--window", window, "1")
    time.sleep(0.4)


def type_text(value):
    command("xdotool", "type", "--window", window, "--delay", "20", value)
    time.sleep(0.3)


def key(name):
    command("xdotool", "key", "--window", window, name)
    time.sleep(0.3)


def capture(name):
    time.sleep(0.4)
    command("import", "-window", window, str(output / f"{name}.png"))


def clipboard():
    return command("xclip", "-selection", "clipboard", "-out")


def tile(index):
    """The centre of a home screen tile; the window is 420 wide."""
    left = (420 - (2 * 120 + 16)) // 2
    return left + (index % 2) * 136 + 60, 56 + 16 + (index // 2) * 136 + 60


def home():
    click(28, 28)


def totp(secret, at):
    key_bytes = base64.b32decode(secret)
    mac = hmac.new(key_bytes, struct.pack(">Q", int(at) // 30), hashlib.sha1).digest()
    offset = mac[-1] & 15
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7fffffff
    return f"{value % 1000000:06d}"


try:
    start()
    capture("home")

    # Pass: the same inputs give the LessPass reference password.
    click(*tile(0))
    capture("pass-open")
    left = (420 - 384) // 2
    click(left + 100, 56 + 12 + 24 + 20)
    type_text("example.com")
    click(left + 100, 56 + 12 + 76 + 24 + 20)
    type_text("alice")
    click(left + 100, 56 + 12 + 152 + 24 + 20)
    type_text("test master")
    capture("pass-filled")
    click(210, 576)
    time.sleep(1.0)
    capture("pass-generated")
    # Generate scrolls to its result; Copy is the last control.
    click(210, 642)
    assert clipboard() == "dEeEDu7/b27L#r<&", "Pass did not copy the LessPass reference password"
    home()

    # Calculator: keyboard input.
    click(*tile(2))
    type_text("12+30*2=")
    capture("calculator")
    home()

    # Clock.
    click(*tile(3))
    capture("clock")
    home()

    # Auth: import a fixture link and copy its code.
    click(*tile(1))
    capture("auth-empty")
    click(210, 56 + 12 + 20)
    click(210, 56 + 12 + 24 + 20)
    type_text(FIXTURE_LINK)
    click(210, 56 + 12 + 76 + 20)
    capture("auth-list")
    before = time.time()
    click(420 - 16 - 10 - 196 + 70 + 16, 56 + 64 + 12 + 22)
    copied = clipboard().strip()
    after = time.time()
    expected = {totp(FIXTURE_SECRET, before), totp(FIXTURE_SECRET, after)}
    assert copied in expected, f"Auth copied {copied!r}, expected one of {sorted(expected)}"
    # The account is a synced record, kept privately and unsynced without
    # an account.
    records = data / "records/auth.txt"
    saved = records.read_text()
    assert FIXTURE_SECRET in saved and "\tV\t1\t" in saved and records.stat().st_mode & 0o077 == 0
    home()

    # Profile: a name and dark appearance are saved privately.
    click(420 - 30, 28)
    click(210, 56 + 16 + 112 + 28 + 20)
    type_text("Fixture Person")
    key("Return")
    click(332, 56 + 16 + 112 + 88 + 32 + 20)
    capture("profile")
    settings = (data / "profile/settings.txt").read_text()
    assert "name=Fixture Person\n" in settings and "theme_mode=2\n" in settings, settings
    assert (data / "profile/settings.txt").stat().st_mode & 0o077 == 0
    stop()
    print("Werk GUI test: home, Pass, Calculator, Clock, Auth and Profile ran on a private display")
finally:
    stop()
