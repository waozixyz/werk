#!/usr/bin/env python3
"""Run Android tests in this repository's disposable, headless emulator."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build/android-emulator"
WORK.mkdir(parents=True, exist_ok=True)
SDK = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "Android/Sdk"))
environment = dict(os.environ)
for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER"):
    environment.pop(key, None)
environment.update(HARMONY_DESKTOP_RECOVERY="0", YUE_DESKTOP_RECOVERY="0",
                   ANDROID_AVD_HOME=str(WORK / "avd"), ANDROID_USER_HOME=str(WORK / "user"),
                   ANDROID_SDK_ROOT=str(SDK), WERK_ANDROID_EMULATOR="emulator-5580")
for key in ("ANDROID_AVD_HOME", "ANDROID_USER_HOME"):
    Path(environment[key]).mkdir(parents=True, exist_ok=True)
avd = WORK / "avd/werk.avd"
if not avd.exists():
    manager = SDK / "cmdline-tools/latest/bin/avdmanager"
    subprocess.run([str(manager), "create", "avd", "--name", "werk", "--package",
                    "system-images;android-31;google_apis;x86_64", "--device", "pixel_2",
                    "--path", str(avd)], input=b"no\n", env=environment, check=True)
for port in (5580, 5581):
    with socket.socket() as probe:
        # A previous owned emulator can leave a TIME_WAIT socket briefly.
        # This still refuses a port held by a live listening process.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
adb = str(SDK / "platform-tools/adb")
environment["PATH"] = str(SDK / "platform-tools") + os.pathsep + environment["PATH"]


def guest(*args, timeout=20):
    return subprocess.run([adb, "-s", environment["WERK_ANDROID_EMULATOR"], *args],
                          env=environment, capture_output=True, timeout=timeout)


with (WORK / "emulator.log").open("wb") as log:
    process = subprocess.Popen([str(SDK / "emulator/emulator"), "-avd", "werk", "-port", "5580",
                                "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot",
                                "-gpu", "swiftshader_indirect", "-memory", "2048", "-cores", "2",
                                "-camera-back", "none", "-camera-front", "none", "-accel", "on"],
                               env=environment, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            assert process.poll() is None, "Private emulator exited; see build/android-emulator/emulator.log"
            if guest("shell", "getprop", "sys.boot_completed").stdout.strip() == b"1":
                break
            time.sleep(2)
        else:
            raise AssertionError("Private emulator did not boot within 300 seconds")
        guest("shell", "wm", "size", "720x1280")
        guest("shell", "wm", "density", "240")
        # These local UI fixtures need no mobile network. Avoid the AVD's
        # delayed SIM setup activity stealing foreground during a test.
        radio = guest("shell", "cmd", "connectivity", "airplane-mode", "enable")
        assert radio.returncode == 0, "Could not isolate the private emulator's mobile radio: " + radio.stderr.decode()
        guest("shell", "input", "keyevent", "82")
        print("Owned headless emulator ready: emulator-5580", flush=True)
        assert sys.argv[1:], "Supply the Android test command"
        result = subprocess.run(sys.argv[1:], cwd=ROOT, env=environment)
        raise SystemExit(result.returncode)
    finally:
        try:
            crash = guest("logcat", "-b", "crash", "-d", "-t", "120", timeout=5)
            (WORK / "crash-logcat.txt").write_bytes(crash.stdout)
        except (OSError, subprocess.TimeoutExpired):
            pass
        # Only the emulator process created above is ours to stop.
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
