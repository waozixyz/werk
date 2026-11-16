#!/usr/bin/env python3
"""Auth cards in Werkzeug's native host, using only private Xvfb and RFC keys."""
from pathlib import Path
import base64
import hashlib
import hmac
import os
import re
import shutil
import struct
import subprocess
import time
from PIL import Image

assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Use private-display.py"
root = Path(__file__).resolve().parents[1]
output = root / "build/auth-gui-test"
shutil.rmtree(output, ignore_errors=True)
data = output / "data"
(data / "profile").mkdir(parents=True)
settings = data / "profile/settings.txt"
settings.write_text("theme_mode=2\n")
environment = dict(os.environ, WERK_DATA=str(data), WERK_ASSETS=str(root / "build"),
                   ENTITY_DATA=str(output / "entity"), XDG_CACHE_HOME=str(output / "cache"),
                   XDG_CONFIG_HOME=str(output / "config"), XDG_DATA_HOME=str(output / "xdg"))
key = b"12345678901234567890"
second_key = b"12345678901234567890123456789012"
links = "\n".join(
    f"otpauth://totp/{issuer}:alice?issuer={issuer}&secret={base64.b32encode(secret).decode()}"
    f"&digits={digits}&period={period}"
    for issuer, secret, digits, period in
    (("Fixture", key, 6, 10), ("Second", second_key, 8, 60)))
subprocess.run([str(root / "build/werk"), "auth", "import"], input=links,
               env=environment, capture_output=True, text=True, check=True, timeout=30)
app = None


def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=20)


def expected(secret, at, digits, period):
    mac = hmac.new(secret, struct.pack(">Q", int(at) // period), hashlib.sha1).digest()
    offset = mac[-1] & 15
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7fffffff
    return f"{value % 10 ** digits:0{digits}d}"


def capture(name):
    target = output / f"{name}.png"
    command("import", "-window", window, str(target))
    return target


def read_code(image, bounds, name):
    target = output / f"{name}.png"
    with Image.open(image) as frame:
        region = frame.crop(bounds)
        region.resize((region.width * 4, region.height * 4)).save(target)
    text = command("tesseract", str(target), "stdout", "--psm", "7",
                   "-c", "tessedit_char_whitelist=0123456789 ").strip()
    assert " " in text, f"No grouping space in {name}: {text!r}"
    return re.sub(r"\s", "", text)


def stop():
    if app is not None and app.poll() is None:
        app.terminate()
        app.wait(timeout=10)


try:
    for dark in (True, False):
        settings.write_text(f"theme_mode={2 if dark else 1}\n")
        app = subprocess.Popen([str(root / "build/werk"), "--app", "auth"], env=environment)
        deadline = time.monotonic() + 30
        window = None
        while time.monotonic() < deadline:
            assert app.poll() is None, "Werkzeug exited"
            found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                                   env=environment, capture_output=True, text=True)
            if found.returncode == 0:
                window = found.stdout.splitlines()[0]
                break
            time.sleep(0.1)
        assert window is not None, "Auth did not show a private window"
        command("xdotool", "windowsize", window, "420", "760")
        command("xdotool", "windowfocus", "--sync", window)
        time.sleep(1)
        before = time.time()
        image = capture("auth-dark" if dark else "auth-light")
        after = time.time()
        with Image.open(image) as frame:
            body = frame.convert("RGB").getpixel((200, 240))
        assert body == ((28, 28, 28) if dark else (242, 240, 245)), body
        for row, secret, digits, period in ((0, key, 6, 10), (1, second_key, 8, 60)):
            y = row * 136
            for label, bounds, offset in (
                    ("current", (32, 184 + y, 236, 230 + y), 0),
                    ("next", (234, 207 + y, 380, 234 + y), period)):
                actual = read_code(image, bounds, f"{label}-{row}-{dark}")
                assert actual in {expected(secret, at + offset, digits, period)
                                  for at in (before, after)}, (row, label, actual)
        before = time.time()
        command("xdotool", "mousemove", "--window", window, "100", "210")
        command("xdotool", "click", "--window", window, "1")
        time.sleep(0.3)
        copied = command("xclip", "-selection", "clipboard", "-o").strip()
        assert copied in {expected(key, at, 6, 10) for at in (before, time.time())}, copied
        if dark:
            # The short fixture period exercises both colours and a new cycle.
            seen = set()
            deadline = time.monotonic() + 13
            while len(seen) < 2 and time.monotonic() < deadline:
                image = capture("progress")
                with Image.open(image) as frame:
                    pixels = frame.convert("RGB")
                    for phase, color in (("purple", (159, 53, 232)), ("orange", (238, 145, 48))):
                        length = sum(pixels.getpixel((x, 121)) == color for x in range(16, 394))
                        if length > 10:
                            assert 187 <= length <= 378 if phase == "purple" else length <= 191
                            seen.add(phase)
                time.sleep(0.2)
            assert seen == {"purple", "orange"}, seen
        stop()
    print("Auth native GUI: grouped current/next codes, raw copy, both bar colours, dark/light cards")
finally:
    stop()
