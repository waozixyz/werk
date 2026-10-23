#!/usr/bin/env python3
"""Run a GUI test under a verified, owned Xvfb server."""
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys

environment = dict(os.environ)
for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER"):
    environment.pop(key, None)
environment["YUE_DESKTOP_RECOVERY"] = "0"
environment["WERK_TEST_PRIVATE_DISPLAY"] = "1"
read_fd, write_fd = os.pipe()
server = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
                          pass_fds=(write_fd,), env=environment)
os.close(write_fd)
try:
    assert select.select([read_fd], [], [], 20)[0], "Xvfb did not allocate a private display"
    display = os.read(read_fd, 32).decode().strip()
    assert display.isdecimal() and server.poll() is None, "Private Xvfb did not start"
    process = Path(f"/proc/{server.pid}")
    executable = process.joinpath("exe").resolve()
    assert executable == Path(shutil.which("Xvfb")).resolve(), "Unexpected X server executable"
    assert process.stat().st_uid == os.getuid(), "Private server has another owner"
    command = process.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode()
    assert f"-displayfd {write_fd} " in command, "Unexpected display allocation source"
    evidence = Path(__file__).resolve().parents[1] / "build/desktop-task"
    evidence.mkdir(parents=True, exist_ok=True)
    with (evidence / "private-displays.log").open("a") as receipt:
        receipt.write(f"pid={server.pid} executable={executable} display=:{display} command={command}\n")
    environment["DISPLAY"] = ":" + display
    print(f"Verified owned private Xvfb for {sys.argv[1]}", flush=True)
    result = subprocess.run(sys.argv[1:], env=environment)
    raise SystemExit(result.returncode)
finally:
    os.close(read_fd)
    if server.poll() is None:
        server.terminate()
    server.wait(timeout=10)
