#!/usr/bin/env python3
"""Verify the shared Apps controller and native tool navigation."""
import csv
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import time
from PIL import Image

assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Use private-display.py"
root = Path(__file__).resolve().parents[1]
work = Path(os.environ.get("WERK_APPS_TEST_OUTPUT", root / "build/apps-gui-test"))
binary = Path(os.environ.get("WERK_TEST_BINARY", root / "build/werk"))
assets = Path(os.environ.get("WERK_TEST_ASSETS", root / "build"))
shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)
expected = (root / "apps-controller.sha256").read_text().strip()
assert hashlib.sha256((assets / "apps/apps.zx").read_bytes()).hexdigest() == expected
environment = dict(os.environ, HOME=str(work / "home"), WERK_DATA=str(work / "data"),
                   WERK_ASSETS=str(assets), ENTITY_DATA=str(work / "entity"),
                   XDG_CONFIG_HOME=str(work / "config"), XDG_DATA_HOME=str(work / "share"),
                   XDG_CACHE_HOME=str(work / "cache"))
for name in ("HOME", "WERK_DATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    Path(environment[name]).mkdir(parents=True)
profile = Path(environment["WERK_DATA"]) / "profile"
profile.mkdir()
(profile / "settings.txt").write_text("theme_mode=1\n")


def command(*arguments):
    return subprocess.check_output(arguments, env=environment, text=True, timeout=20)


def capture(name):
    time.sleep(.3)
    picture = work / (name + ".png")
    command("import", "-window", window, str(picture))
    # Separate dark text from the soft card fills for reliable recognition.
    with Image.open(picture) as source:
        labels = source.convert("L").point(lambda value: 0 if value < 140 else 255)
        labels.resize((source.width * 3, source.height * 3)).save(work / "labels.png")
        source.resize((source.width * 3, source.height * 3)).save(work / "full-text.png")
    return command("tesseract", str(work / "labels.png"), "stdout", "--psm", "11")


def click(x, y):
    command("xdotool", "mousemove", "--window", window, str(x), str(y))
    command("xdotool", "click", "--window", window, "1")
    time.sleep(.2)


def word_position(word):
    capture("control")
    for target in ("labels.png", "full-text.png"):
        text = command("tesseract", str(work / target), "stdout", "--psm", "11",
                       "-c", "tessedit_create_tsv=1")
        for item in csv.DictReader(io.StringIO(text), delimiter="\t"):
            if item["text"].strip() == word:
                return ((int(item["left"]) + int(item["width"]) // 2) // 3,
                        (int(item["top"]) + int(item["height"]) // 2) // 3)
    raise AssertionError("Missing visible app control: " + word)


def click_word(word):
    click(*word_position(word))


def key(value):
    command("xdotool", "key", "--window", window, value)
    time.sleep(.2)


def type_text(value):
    command("xdotool", "type", "--window", window, "--delay", "30", value)
    time.sleep(.3)


def expect_title(expected):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        assert app.poll() is None, "Werkzeug exited during navigation"
        title = command("xdotool", "getwindowname", window).strip()
        if title == expected:
            return
        time.sleep(.1)
    capture("navigation-failure")
    raise AssertionError(f"Expected window title {expected!r}, got {title!r}")


app = subprocess.Popen([str(binary)], env=environment)
try:
    deadline = time.monotonic() + 30
    window = None
    while time.monotonic() < deadline:
        assert app.poll() is None, "Werkzeug exited during startup"
        found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                               env=environment, capture_output=True, text=True, timeout=5)
        if found.returncode == 0:
            window = found.stdout.splitlines()[0]
            break
        time.sleep(.1)
    assert window, "Werkzeug did not show its owned window"
    command("xdotool", "windowfocus", "--sync", window)
    # Window creation precedes loading the portable apps and the first frame.
    deadline = time.monotonic() + 20
    while True:
        home = capture("home")
        if all(name in home for name in ("Pass", "Auth", "Calculator", "Clock", "Workbook")):
            break
        assert app.poll() is None, "Werkzeug exited while loading Apps"
        assert time.monotonic() < deadline, "Shared Apps controller did not render: " + home
    assert not re.search(r"\d[\d.]*\s*(?:kB|MB)\b", home, re.I), home
    for name in ("Auth", "Calculator", "Clock", "Workbook", "Pass"):
        click_word(name)
        expect_title(name)
        assert "stopped" not in capture(name.lower()).lower(), name + " failed to run"
        click(28, 28)
        expect_title("Werkzeug")
    for width, height in ((360, 640), (720, 520)):
        command("xdotool", "windowsize", "--sync", window, str(width), str(height))
        text = capture(f"home-{width}")
        assert all(name in text for name in ("Pass", "Auth", "Calculator", "Clock", "Workbook")), text
    command("xdotool", "windowsize", "--sync", window, "420", "760")
    time.sleep(.3)
    click(330, 92)  # Shared List view control, beside the search field.
    preferences = Path(environment["WERK_DATA"]) / "profile/apps.json"
    assert json.loads(preferences.read_text())["list"] is True
    text = capture("list")
    assert all(name in text for name in ("Pass", "Auth", "Calculator", "Clock", "Workbook")), text
    assert not re.search(r"\d[\d.]*\s*(?:kB|MB)\b", text, re.I), text
    click(100, 92)
    type_text("clock")
    text = capture("search")
    assert "Clock" in text and "Calculator" not in text and "Workbook" not in text, text
    click(278, 92)  # Clear search is part of the shared field.
    assert "Calculator" in capture("search-cleared")
    click(382, 372)  # Clock's options at the end of its list row.
    text = capture("options")
    assert all(label in text for label in ("Open", "Pin", "Properties")), text
    click_word("Pin")
    capture("pinned")
    saved = json.loads(preferences.read_text())
    assert next(item for item in saved["apps"] if item["id"] == "clock")["favorite"]
    click(382, 204)  # Clock now appears first, in Pinned.
    assert "Unpin" in capture("pinned-options")
    click_word("Properties")
    name = word_position("Name")
    click(120, name[1] + 34)
    key("ctrl+a")
    type_text("Timepiece")
    # The icon choices are: own icon, then Pass, Auth, Calculator, Clock, Workbook.
    click(name[0] - 16 + 120, name[1] + 116)
    # White text on the filled Save button is not reliably recognized by OCR.
    click(310, name[1] + 182)
    saved = json.loads(preferences.read_text())
    clock = next(item for item in saved["apps"] if item["id"] == "clock")
    assert clock["title"] == "Timepiece" and clock["icon"] == "auth", clock
    assert "Timepiece" in capture("renamed")
    assert preferences.stat().st_mode & 0o777 == 0o600
    app.terminate()
    app.wait(timeout=10)
    app = subprocess.Popen([str(binary)], env=environment)
    deadline = time.monotonic() + 30
    while True:
        found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                               env=environment, capture_output=True, text=True, timeout=5)
        if found.returncode == 0:
            window = found.stdout.splitlines()[0]
            if "Timepiece" in capture("restarted"):
                break
        assert time.monotonic() < deadline, "Launcher preferences did not survive restart"
        time.sleep(.1)
    click(382, 204)
    click_word("Open")
    assert command("xdotool", "getwindowname", window).strip() == "Clock"
    click(28, 28)
    click(382, 204)
    click_word("Unpin")
    saved = json.loads(preferences.read_text())
    clock = next(item for item in saved["apps"] if item["id"] == "clock")
    assert not clock["favorite"] and clock["title"] == "Timepiece" and clock["icon"] == "auth"
    print("Shared Apps: list/grid, search, menus, pins, name/icon edits, restart persistence, five tools and resized layouts verified locally")
finally:
    if app.poll() is None:
        app.terminate()
    app.wait(timeout=10)
