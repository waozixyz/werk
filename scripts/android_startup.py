"""Wait for visible Home on an explicitly selected private Android emulator."""
import re
import shutil
import time
import xml.etree.ElementTree as ET

from android_labels import label_position


def wait_for_system_ui(adb, frame, output):
    # Preserve evidence and wait only for the observed system dialog. An app
    # ANR must remain a test failure.
    if not label_position(frame, "Wait"):
        return False
    path = "/data/local/tmp/werk-startup-window.xml"
    adb("shell", "rm", "-f", path)
    dumped = adb("shell", "uiautomator", "dump", "--compressed", path, check=False)
    if dumped.returncode:
        return False
    tree = adb("shell", "cat", path, check=False)
    if tree.returncode:
        return False
    data = tree.stdout.decode()
    if "System UI isn" not in data or "responding" not in data:
        return False
    try:
        nodes = ET.fromstring(data).iter("node")
    except ET.ParseError:
        return False
    for node in nodes:
        if node.get("text") == "Wait":
            bounds = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
            if len(bounds) == 4:
                shutil.copyfile(frame, output / "system-ui-dialog.png")
                (output / "system-ui-window.xml").write_text(data)
                print("Waiting for the private guest's System UI", flush=True)
                adb("shell", "input", "tap", str((bounds[0] + bounds[2]) // 2),
                    str((bounds[1] + bounds[3]) // 2))
                return True
    return False


def launch_home(adb, output, package, name, timeout=180):
    launch = adb("shell", "am", "start", "-W", "-n",
                 package + "/android.app.NativeActivity").stdout.decode()
    (output / (name + ".txt")).write_text(launch)
    # Android's launch metric can time out before a cold software guest draws
    # its first frame. Require visible Home before interacting with its list.
    deadline = time.monotonic() + timeout
    system_waits = 0
    while time.monotonic() < deadline:
        frame = output / (name + "-home.png")
        frame.write_bytes(adb("exec-out", "screencap", "-p").stdout)
        if any(label_position(frame, word) for word in ("Werkzeug", "Pass", "Auth", "Calculator")):
            print("Android Home visible after " + name, flush=True)
            return
        if system_waits == 0 and wait_for_system_ui(adb, frame, output):
            system_waits = 1
        time.sleep(.5)
    raise AssertionError("Android Home did not become visible after " + name + ": " + launch)
