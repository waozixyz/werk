#!/usr/bin/env python3
"""Launch the installed desktop entries against disposable private data."""
import configparser
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time

assert os.environ.get("WERK_TEST_PRIVATE_DISPLAY") == "1", "Use private-display.py"
root = Path(__file__).resolve().parents[1]
work = root / "build/launcher-gui-test"
shutil.rmtree(work, ignore_errors=True)
stage = work / "install with spaces"
share = stage / "share"
desktop = stage / "Desktop"
library = stage / "lib/werk"
subprocess.run(["make", "install-gui", f"BIN_DIR={stage / 'bin'}", f"DATA_DIR={share}",
                f"LIB_DIR={library}", f"DESKTOP_DIR={desktop}"], cwd=root, check=True)
environment = dict(os.environ, HOME=str(work / "home"), WERK_DATA=str(work / "data"),
                   WERK_ASSETS=str(library), ENTITY_DATA=str(work / "entity"),
                   XDG_DATA_HOME=str(share), XDG_CONFIG_HOME=str(work / "config"),
                   XDG_CACHE_HOME=str(work / "cache"))
for key in ("HOME", "WERK_DATA", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    Path(environment[key]).mkdir(parents=True, exist_ok=True)
profile = work / "data/profile"
profile.mkdir(parents=True)
(profile / "settings.txt").write_text("theme_mode=1\n")


def command(*args):
    return subprocess.check_output(args, env=environment, text=True, timeout=20)


for tool, name in (("", "Werkzeug"), ("pass", "Pass"), ("auth", "Auth"),
                   ("calculator", "Calculator"), ("clock", "Clock"), ("workbook", "Workbook")):
    identity = "xyz.waozi.werk" + ("." + tool if tool else "")
    entry = share / "applications" / (identity + ".desktop")
    assert entry.read_bytes() == (desktop / entry.name).read_bytes()
    assert (desktop / entry.name).stat().st_mode & 0o100
    subprocess.run(["desktop-file-validate", str(entry)], check=True)
    config = configparser.ConfigParser(interpolation=None)
    config.read(entry)
    values = config["Desktop Entry"]
    assert values["Name"] == name
    assert (share / "icons/hicolor/512x512/apps" / (values["Icon"] + ".png")).is_file()
    argv = shlex.split(values["Exec"])
    if not tool:
        argv = argv[:1]
    process = subprocess.Popen(argv, env=environment)
    try:
        window = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            assert process.poll() is None, f"{name} exited during startup"
            result = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(process.pid)],
                                    env=environment, text=True, capture_output=True)
            if result.returncode == 0:
                window = result.stdout.splitlines()[0]
                if command("xdotool", "getwindowname", window).strip() == name:
                    break
            time.sleep(.1)
        assert window and command("xdotool", "getwindowname", window).strip() == name
        wm_class = command("xprop", "-id", window, "WM_CLASS")
        assert values["StartupWMClass"] in wm_class, wm_class
        time.sleep(.5)
        picture = work / ((tool or "werkzeug") + ".png")
        command("import", "-window", window, str(picture))
        text = command("tesseract", str(picture), "stdout", "--psm", "11")
        assert name in text, f"{name} did not render its direct tool screen: {text}"
        assert "unavailable" not in text.lower(), text
        print(f"Installed {name} entry opened the correct screen and window identity", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)

subprocess.run(["python3", str(root / "scripts/install-launchers.py"), "--data-dir", str(share),
                "--desktop-dir", str(desktop), "--uninstall"], check=True)
assert not list((share / "applications").glob("xyz.waozi.werk*.desktop"))
assert not list(desktop.glob("xyz.waozi.werk*.desktop"))
print("All six installed launchers, distinct icons and shortcut removal verified locally")
