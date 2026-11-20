#!/usr/bin/env python3
"""Auth cards in Werkzeug's native host, using only private Xvfb and RFC keys."""
from pathlib import Path
import base64
import hashlib
import hmac
import os
import re
import shutil
import statistics
import struct
import subprocess
import time
from PIL import Image, ImageOps

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


def read_code(image, bounds, name, expected_codes=None):
    target = output / f"{name}.png"
    with Image.open(image) as frame:
        region = frame.crop(bounds).convert("L")
        if region.getpixel((0, 0)) < 128:
            region = ImageOps.invert(region)
        region = ImageOps.autocontrast(region)
    # Small preview glyphs differ between installed fonts, and Tesseract reads
    # a large current-code 5 as 0 or 9 at some scales. Require an exact
    # independently computed RFC code from real OCR, with no digit substitution.
    first = None
    variants = ((scale, threshold) for scale in (6, 3, 4) for threshold in (None, 150, 110, 190))
    for scale, threshold in variants:
        variant = region.resize((region.width * scale, region.height * scale), Image.Resampling.LANCZOS)
        if threshold is not None:
            variant = variant.point(lambda value: 255 if value > threshold else 0)
        variant.save(target)
        text = command("tesseract", str(target), "stdout", "--psm", "7",
                       "-c", "preserve_interword_spaces=1",
                       "-c", "tessedit_char_whitelist=0123456789 ").strip()
        if first is None:
            first = text
        if expected_codes is None or re.sub(r"\s", "", text) in expected_codes:
            break
    else:
        raise AssertionError(f"{name}: OCR {first!r}, expected one of {sorted(expected_codes)}")
    digits = re.sub(r"\s", "", text)
    if " " not in text:
        # OCR sometimes joins a real grouping space. Character positions
        # must still show the extra gaps separating each group of three digits.
        boxes = command("tesseract", str(target), "stdout", "--psm", "7",
                        "-c", "tessedit_char_whitelist=0123456789", "makebox")
        centers = [(int(parts[1]) + int(parts[3])) / 2
                   for line in boxes.splitlines()
                   if len(parts := line.split()) == 6 and parts[0].isdigit()]
        assert len(centers) == len(digits) and len(digits) in (6, 8), boxes
        steps = [right - left for left, right in zip(centers, centers[1:])]
        separators = set(range(2, len(steps), 3))
        ordinary = [step for index, step in enumerate(steps) if index not in separators]
        assert all(steps[index] > statistics.median(ordinary) + 6 for index in separators), f"No visible grouping gap in {name}: {steps}"
    return digits


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
                wanted = {expected(secret, at + offset, digits, period) for at in (before, after)}
                actual = read_code(image, bounds, f"{label}-{row}-{dark}", wanted)
                assert actual in wanted, (row, label, actual)
        # Background, title, account, current code, preview and bottom padding.
        for x, y in ((20, 124), (70, 146), (70, 169), (100, 210), (340, 220), (390, 244)):
            subprocess.run(["xclip", "-selection", "clipboard", "-i"],
                           input="fixture-before-card", text=True, env=environment,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True, timeout=20)
            before = time.time()
            command("xdotool", "mousemove", "--window", window, str(x), str(y))
            command("xdotool", "click", "1")
            time.sleep(0.15)
            copied = command("xclip", "-selection", "clipboard", "-o")
            assert re.fullmatch(r"[0-9]{6}", copied), (x, y, copied)
            assert copied in {expected(key, at, 6, 10) for at in (before, time.time())}, (x, y, copied)
        toast = output / f"copy-toast-text-{dark}.png"
        with Image.open(capture(f"copy-toast-{dark}")) as frame:
            center = frame.width // 2
            region = frame.crop((center - 105, frame.height - 66, center + 105, frame.height - 4)).convert("L")
            if dark:
                region = ImageOps.invert(region)
            region = ImageOps.autocontrast(region)
            region.resize((region.width * 4, region.height * 4), Image.Resampling.LANCZOS).save(toast)
        text = command("tesseract", str(toast), "stdout", "--psm", "11")
        assert "Copied to clipboard" in text, text
        # Edit remains independently clickable and never overwrites the clipboard.
        before_edit = copied
        command("xdotool", "mousemove", "--window", window, "370", "146")
        command("xdotool", "click", "1")
        time.sleep(0.2)
        assert command("xclip", "-selection", "clipboard", "-o") == before_edit
        edit_image = capture("edit-dark" if dark else "edit-light")
        text = command("tesseract", str(edit_image), "stdout", "--psm", "11")
        assert "Remove account" in text, text
        # Sparse-page OCR skips small labels inside filled buttons. Read the
        # actual action in isolation, with enough contrast in either theme.
        cancel_image = output / f"cancel-{dark}.png"
        with Image.open(edit_image) as frame:
            action = frame.crop((214, 252, 404, 292)).convert("L")
            if dark:
                action = ImageOps.invert(action)
            action.resize((action.width * 6, action.height * 6)).save(cancel_image)
        assert command("tesseract", str(cancel_image), "stdout", "--psm", "7").strip() == "Cancel"
        command("xdotool", "mousemove", "--window", window, "309", "272")
        command("xdotool", "click", "1")
        time.sleep(0.2)
        returned = capture(f"after-cancel-{dark}")
        assert re.fullmatch(r"[0-9]{6}", read_code(returned, (32, 184, 236, 230), f"returned-{dark}"))
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
    print("Auth native GUI: grouped current/next codes, raw copy and toast, both bar colours, dark/light cards")
finally:
    stop()
