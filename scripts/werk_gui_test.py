#!/usr/bin/env python3
"""Drive Werkzeug and its four apps on the harness's private Xvfb display.

Uses disposable data and cache folders and fixture secrets only. Run
through scripts/werk_gui_test.sh, which starts the private display.
"""
from pathlib import Path
import csv
import io
import json
import base64
import hashlib
import hmac
import os
import shutil
import struct
import subprocess
import time
from PIL import Image

assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Run scripts/werk_gui_test.sh"
root = Path(__file__).resolve().parents[1]
output = root / "build/werk-gui-test"
shutil.rmtree(output, ignore_errors=True)
data = output / "data"
cache = output / "cache"
data.mkdir(parents=True)
cache.mkdir(parents=True)
(data / "profile").mkdir()
(data / "profile/settings.txt").write_text("name=Fixture Person\ntheme_mode=1\n")
environment = dict(os.environ)
environment.pop("WAYLAND_DISPLAY", None)
environment["WERK_DATA"] = str(data)
environment["ENTITY_DATA"] = str(output / "shared-entity")
environment["XDG_DATA_HOME"] = str(output / "xdg-data")
environment["XDG_CONFIG_HOME"] = str(output / "xdg-config")
environment["XDG_CACHE_HOME"] = str(cache)
environment["WERK_ASSETS"] = str(root / "build")
# Import file runs zenity; this stand-in chooses a fixture Aegis export.
fake_bin = output / "bin"
fake_bin.mkdir()
(fake_bin / "zenity").write_text('#!/bin/sh\nprintf "%s\\n" "$WERK_TEST_IMPORT_FILE"\n')
(fake_bin / "zenity").chmod(0o755)
environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
environment["WERK_TEST_IMPORT_FILE"] = str(output / "aegis.json")
app = None
window = None

# The RFC 6238 SHA-1 fixture key, never a real account.
FIXTURE_SECRET = base64.b32encode(b"12345678901234567890").decode()
FIXTURE_LINK = f"otpauth://totp/Fixture:alice@example.com?secret={FIXTURE_SECRET}&issuer=Fixture"
# A Google Authenticator export of the same key, an RFC 6238 SHA-256 key and
# a counter-based account (see apps/auth/exports_test.zi).
MIGRATION_LINK = ("otpauth-migration://offline?data=CjoKFDEyMzQ1Njc4OTAxMjM0NTY3ODkwEhxFeGFtcGxlIENvOmFsaWNl"
                  "QGV4YW1wbGUuY29tIAEoATACCjUKIDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyEgNib2IaBlNlY29uZCAC"
                  "KAIwAgorChQxMjM0NTY3ODkwMTIzNDU2Nzg5MBIHY291bnRlchoESG90cCABKAEwARABGAEgACi5YA%3D%3D")


def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=20)


def start():
    global app, window
    app = subprocess.Popen([str(root / "build/werk")], env=environment)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert app.poll() is None, "Werkzeug exited before showing its window"
        found = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(app.pid)],
                               env=environment, capture_output=True, text=True)
        if found.returncode == 0:
            window = found.stdout.splitlines()[0]
            command("xdotool", "windowfocus", "--sync", window)
            ready = time.monotonic() + 20
            while time.monotonic() < ready:
                assert app.poll() is None, "Werkzeug exited while loading its tools"
                capture("startup")
                with Image.open(output / "startup.png") as source:
                    labels = source.convert("L").point(lambda value: 0 if value < 140 else 255)
                    labels.resize((source.width * 3, source.height * 3)).save(output / "startup-labels.png")
                text = command("tesseract", str(output / "startup-labels.png"), "stdout", "--psm", "11")
                if all(name in text for name in ("Pass", "Auth", "Calculator", "Clock")):
                    return
            raise AssertionError("Werkzeug did not finish drawing its home screen")
        time.sleep(0.1)
    raise AssertionError("Werkzeug did not show its window")


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


def click_word(word, toggle=False, last=False, exact_case=False):
    capture("control")
    for factor, labels in ((1, False), (3, False), (3, True)):
        target = output / "control.png"
        if factor > 1:
            target = output / "control-enlarged.png"
            with Image.open(output / "control.png") as source:
                readable = source.convert("L").point(lambda value: 0 if value < 140 else 255) if labels else source
                readable.resize((source.width * factor, source.height * factor)).save(target)
        text = command("tesseract", str(target), "stdout", "--psm", "11",
                       "-c", "tessedit_create_tsv=1")
        matches = [item for item in csv.DictReader(io.StringIO(text), delimiter="\t") if (item["text"].strip() == word if exact_case else item["text"].strip().lower() == word.lower())]
        if last: matches.reverse()
        for item in matches:
            if item["text"].strip().lower() == word.lower():
                click(350 if toggle else (int(item["left"]) + int(item["width"]) // 2) // factor,
                      (int(item["top"]) + int(item["height"]) // 2) // factor)
                return ((int(item["left"]) + int(item["width"]) // 2) // factor,
                        (int(item["top"]) + int(item["height"]) // 2) // factor)
    raise AssertionError(f"Could not find {word!r} in the private test window")


def click_scrolled(word, **options):
    for attempt in range(12):
        try:
            return click_word(word, **options)
        except AssertionError:
            command("xdotool", "mousemove", "--window", window, "200", "650")
            command("xdotool", "click", "--window", window, "--repeat", "3", "--delay", "50", "5")
            time.sleep(.2)
    raise AssertionError("Missing scrollable control: " + word)


def click_filled():
    capture("filled-control")
    with Image.open(output / "filled-control.png") as source:
        pixels = source.convert("RGB")
        rows = []
        for y in range(56, pixels.height):
            span = [x for x in range(pixels.width)
                    if min(pixels.getpixel((x, y))) < 120
                    and max(pixels.getpixel((x, y))) < 220
                    and max(pixels.getpixel((x, y))) - min(pixels.getpixel((x, y))) > 40]
            if len(span) > 200:
                rows.append((min(span), y, max(span)))
        assert rows, "Missing filled account action"
    click((rows[0][0] + rows[0][2]) // 2, (rows[0][1] + rows[-1][1]) // 2)


def screen_text():
    capture("control")
    return command("tesseract", str(output / "control.png"), "stdout", "--psm", "11")


def field_below(word, offset=40):
    capture("control")
    text = command("tesseract", str(output / "control.png"), "stdout", "--psm", "11", "-c", "tessedit_create_tsv=1")
    for item in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if item["text"].strip() == word:
            return int(item["left"]) + 80, int(item["top"]) + offset
    raise AssertionError("Missing field label: " + word)


def scroll_up():
    command("xdotool", "mousemove", "--window", window, "210", "400")
    command("xdotool", "click", "--window", window, "--repeat", "18", "--delay", "40", "4")
    time.sleep(.4)


def add_node(field):
    # The private fixture window is 420 units wide; the Add button shares
    # the node field row and remains visible with either appearance/accent.
    click(344, field[1])


def scroll_down():
    command("xdotool", "mousemove", "--window", window, "210", "650")
    command("xdotool", "click", "--window", window, "--repeat", "12", "--delay", "70", "5")
    time.sleep(0.4)


def clipboard():
    return command("xclip", "-selection", "clipboard", "-out")


def open_tool(name):
    click_word(name, exact_case=True)
    assert command("xdotool", "getwindowname", window).strip() == name


def home():
    click(28, 28)


def totp(secret, at):
    key_bytes = base64.b32decode(secret)
    mac = hmac.new(key_bytes, struct.pack(">Q", int(at) // 30), hashlib.sha1).digest()
    offset = mac[-1] & 15
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7fffffff
    return f"{value % 1000000:06d}"


def import_invalid_key():
    # Select an invalid fixture through the real native key chooser.
    # Both the dialog and the main window belong to this test process.
    scroll_up()
    click_word("Import")
    click_filled()
    dialog = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        found = command("xdotool", "search", "--onlyvisible", "--pid", str(app.pid)).splitlines()
        for candidate in found:
            if candidate != window and command("xdotool", "getwindowname", candidate).strip() == "Import account key":
                dialog = candidate
                break
        if dialog: break
        time.sleep(.1)
    assert dialog, "Native account file chooser did not open"
    invalid_key = output / "invalid-account.key"
    invalid_key.write_text("fixture: not an account key")
    command("xdotool", "windowfocus", "--sync", dialog)
    command("xdotool", "key", "--clearmodifiers", "ctrl+l")
    time.sleep(.3)
    command("xdotool", "type", "--clearmodifiers", "--delay", "5", str(invalid_key))
    command("xdotool", "key", "--clearmodifiers", "Return")
    time.sleep(1)
    visible = command("xdotool", "search", "--onlyvisible", "--pid", str(app.pid)).splitlines()
    if dialog in visible:
        geometry = dict(item.split("=", 1) for item in command("xdotool", "getwindowgeometry", "--shell", dialog).splitlines())
        command("xdotool", "mousemove", "--window", dialog, str(int(geometry["WIDTH"]) - 50), str(int(geometry["HEIGHT"]) - 24))
        command("xdotool", "click", "1")
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        found = command("xdotool", "search", "--onlyvisible", "--pid", str(app.pid)).splitlines()
        if dialog not in found: break
        time.sleep(.2)
    if dialog in found:
        command("xdotool", "windowraise", window)
        command("xdotool", "windowfocus", "--sync", window)
        time.sleep(1)
        capture("chooser-main-after-selection")
    assert dialog not in found, "Native file selection did not finish"
    command("xdotool", "windowfocus", "--sync", window)
    time.sleep(1)
    assert not (data / "account/keys.txt").exists(), "An invalid key created an account"
    assert "notvalid" in "".join(screen_text().split()), "Invalid key error was not shown"
    capture("invalid-account-refused")


try:
    start()
    if os.environ.get("WERK_GUI_CHOOSER_ONLY") == "1":
        click(390, 28)
        click_word("Connect", exact_case=True)
        import_invalid_key()
        print("Native key chooser selected the invalid fixture and returned its validation error")
        raise SystemExit(0)
    capture("home")

    # Pass: the same inputs give the LessPass reference password.
    open_tool("Pass")
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
    open_tool("Calculator")
    type_text("12+30*2=")
    capture("calculator")
    assert "72" in screen_text(), "Calculator did not show the expected result"
    home()

    # Clock.
    open_tool("Clock")
    capture("clock")
    click_word("Stopwatch")
    click(110, 382)
    time.sleep(1.2)
    click(110, 382)
    stopwatch = next(data.rglob("stopwatch.txt"))
    state = [int(value) for value in stopwatch.read_text().split()]
    assert state[0] == 0 and state[2] >= 1000, "Stopwatch did not advance and stop"
    capture("stopwatch")
    click(310, 382)
    assert stopwatch.read_text().split() == ["0", "0", "0"], "Stopwatch did not reset"
    home()

    # Auth: import a fixture link and copy its code.
    open_tool("Auth")
    capture("auth-empty")
    click(210, 56 + 12 + 20)
    click(210, 56 + 12 + 24 + 20)
    type_text(FIXTURE_LINK)
    click(16 + 95, 56 + 12 + 76 + 20)
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
    # A Google Authenticator export adds its new time-based account; the
    # fixture key is already here and the counter-based one is skipped.
    click(210, 56 + 12 + 20)
    click(210, 56 + 12 + 24 + 20)
    type_text(MIGRATION_LINK)
    click(16 + 95, 56 + 12 + 76 + 20)
    capture("auth-imported")
    saved = records.read_text()
    assert saved.count("\tV\t") == 2 and "Second:bob" in saved, saved.count("\tV\t")
    # Edit renames the account and keeps the websites where it signs in, in
    # the same record.
    edit = (420 - 16 - 10 - 40 + 18, 56 + 64 + 16 + 18)
    click(*edit)
    capture("auth-edit")
    click(210, 56 + 12 + 48 + 20)
    key("ctrl+a")
    type_text("renamed@example.com")
    click(210, 56 + 12 + 48 + 56 + 24 + 20)
    type_text("https://GitHub.com/login")
    click(16 + 95, 56 + 12 + 48 + 56 + 24 + 56 + 20)
    capture("auth-edited")
    saved = records.read_text()
    assert saved.count("\tV\t") == 2 and "Fixture:renamed%40example.com" in saved and "&sites=github.com" in saved
    # Remove, inside Edit, needs a second tap.
    click(*edit)
    remove = (210, 56 + 12 + 48 + 56 + 24 + 56 + 64 + 20)
    click(*remove)
    assert "\tD\t" not in records.read_text(), "One tap removed an Auth account"
    click(*remove)
    capture("auth-removed")
    saved = records.read_text()
    assert saved.count("\tV\t") == 1 and saved.count("\tD\t") == 1 and "Second:bob" in saved
    # Import file reads an export the owner chooses.
    (output / "aegis.json").write_text(json.dumps({"version": 1, "header": {"slots": None}, "db": {"version": 2, "entries": [
        {"type": "totp", "name": "carol", "issuer": "Third",
         "info": {"secret": FIXTURE_SECRET, "algo": "SHA1", "digits": 6, "period": 30}}]}}))
    click(210, 56 + 12 + 20)
    click(16 + 190 + 8 + 95, 56 + 12 + 76 + 20)
    capture("auth-file-imported")
    saved = records.read_text()
    assert saved.count("\tV\t") == 2 and "Third:carol" in saved, saved.count("\tV\t")
    home()

    # Entity retains existing names; its current profile edits appearance.
    assert "name=Fixture Person\n" in (data / "profile/settings.txt").read_text()
    click(390, 28)
    scroll_down()
    click_word("Dark")
    capture("profile")
    settings = (data / "profile/settings.txt").read_text()
    assert "name=Fixture Person\n" in settings and "theme_mode=2\n" in settings, settings
    assert (data / "profile/settings.txt").stat().st_mode & 0o077 == 0
    # Nodes belong to the common Entity bundle; choosing one creates no account.
    click_word("Light")
    scroll_up()
    click_word("Connect", exact_case=True)
    node_field = field_below("Nodes", 120)
    click(*node_field)
    type_text("https://example.invalid/path")
    add_node(node_field)
    assert "node=https://api.waozi.xyz\n" in (data / "profile/settings.txt").read_text()
    capture("node-invalid")
    click(*node_field)
    key("ctrl+a")
    type_text("https://sync.example.invalid:8443/")
    add_node(node_field)
    assert "node=https://sync.example.invalid:8443\n" in (data / "profile/settings.txt").read_text()
    assert not (data / "account/keys.txt").exists(), "Choosing a node created an account"
    capture("node-saved")
    stop()
    start()
    click(390, 28)
    click_word("Connect", exact_case=True)
    capture("node-restarted")
    assert "node=https://sync.example.invalid:8443\n" in (data / "profile/settings.txt").read_text()
    assert not (data / "account/keys.txt").exists()
    scroll_up()
    # The filled action's painted bounds are stable even when OCR misses
    # white labels. Creating an account explicitly asks to merge Auth data.
    click_filled()
    time.sleep(.8)
    click_word("merge", last=True)
    time.sleep(.8)
    account_file = data / "account/keys.txt"
    assert account_file.exists() and "paused=0\n" in account_file.read_text()
    click_scrolled("Sync", toggle=True)
    assert "paused=1\n" in account_file.read_text(), "Entity's sync switch did not pause"
    capture("sync-paused")
    stop()
    start()
    assert "paused=1\n" in account_file.read_text()
    click(390, 28)
    # Use the visible account-management action after a restart.
    click_scrolled("Manage", exact_case=True)
    capture("sync-paused-restarted")
    previous_account = account_file.read_text()
    scroll_down()
    node_field = click_scrolled("address")
    type_text("https://second.example.invalid")
    add_node(node_field)
    account = account_file.read_text()
    assert "server=https://second.example.invalid\n" in account, "The account kept its old node"
    assert "paused=1\n" in account, "Changing node resumed a paused account"
    assert ([line for line in previous_account.splitlines() if not line.startswith("server=")]
            == [line for line in account.splitlines() if not line.startswith("server=")]), "Changing node altered account credentials"
    scroll_up()
    click_scrolled("out")
    click_filled()
    time.sleep(.8)
    assert not account_file.exists()
    assert records.read_text() == saved, "Logging out changed local Auth records"
    capture("account-logged-out")
    import_invalid_key()
    stop()
    print("Werkzeug GUI test: home, Pass, Calculator, Clock, Auth and Profile ran on a private display")
finally:
    stop()
