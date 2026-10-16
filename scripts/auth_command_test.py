#!/usr/bin/env python3
"""`werk auth …` and `werk sync status` without a window, on disposable data.

Uses fixture keys only (RFC 6238's) and never a display: DISPLAY and the
other session variables are removed, so a window could not open.
"""
from pathlib import Path
import base64
import hashlib
import hmac
import json
import os
import shutil
import struct
import subprocess
import time

root = Path(__file__).resolve().parents[1]
werk = root / "build/werk"
output = root / "build/auth-command-test"
shutil.rmtree(output, ignore_errors=True)
data = output / "data"
data.mkdir(parents=True)
environment = {key: value for key, value in os.environ.items()
               if key not in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS")}
environment["WERK_DATA"] = str(data)
# No account exists, so nothing may reach this unreachable node.
environment["WERK_SYNC_SERVER"] = "https://sync.example.invalid"

SECRET = base64.b32encode(b"12345678901234567890").decode()
FIXTURE = f"otpauth://totp/Fixture:alice?secret={SECRET}&issuer=Fixture"
# Example Co:alice@example.com (the same key), Second:bob (SHA-256, 8 digits)
# and a counter-based account, as Google Authenticator exports them.
MIGRATION = ("otpauth-migration://offline?data=CjoKFDEyMzQ1Njc4OTAxMjM0NTY3ODkwEhxFeGFtcGxlIENvOmFsaWNl"
             "QGV4YW1wbGUuY29tIAEoATACCjUKIDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyEgNib2IaBlNlY29uZCAC"
             "KAIwAgorChQxMjM0NTY3ODkwMTIzNDU2Nzg5MBIHY291bnRlchoESG90cCABKAEwARABGAEgACi5YA%3D%3D")
AEGIS = json.dumps({"version": 1, "header": {"slots": None, "params": None}, "db": {"version": 2, "entries": [
    {"type": "totp", "name": "carol", "issuer": "Third",
     "info": {"secret": SECRET, "algo": "SHA1", "digits": 7, "period": 60}}]}})
AEGIS_ENCRYPTED = json.dumps({"version": 1, "header": {"slots": [{"type": 1}], "params": {}}, "db": "c2VhbGVk"})


def run(*args, stdin="", status=0):
    result = subprocess.run([str(werk), *args], env=environment, input=stdin, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == status, (args, result.returncode, result.stdout, result.stderr)
    assert SECRET not in result.stdout + result.stderr, "a secret reached the output"
    return result.stdout


def accounts():
    listed = json.loads(run("auth", "list"))
    return {entry["issuer"]: entry for entry in listed}


def totp(secret, at, digits=6, period=30, digest=hashlib.sha1):
    key = base64.b32decode(secret)
    mac = hmac.new(key, struct.pack(">Q", int(at) // period), digest).digest()
    offset = mac[-1] & 15
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7fffffff
    return f"{value % 10 ** digits:0{digits}d}"


run("auth", status=2)
assert run("sync", "status") == "Account: none on this device\nAuth accounts: 0\n"

# Links and Google's export: the second copy of the key and the counter
# account are left out.
assert run("auth", "import", stdin=f"{FIXTURE}\n{MIGRATION}\n") == "Added 2 accounts, skipped 1\n"
listed = accounts()
assert sorted(listed) == ["Fixture", "Second"], listed
assert listed["Second"]["digits"] == 8 and listed["Fixture"]["sites"] == []
fixture = listed["Fixture"]["id"]
records = data / "records/auth.txt"
assert records.stat().st_mode & 0o077 == 0 and SECRET in records.read_text()

# The code, and how long it stays valid.
before = time.time()
code, seconds = run("auth", "code", fixture).split()
after = time.time()
assert code in {totp(SECRET, before), totp(SECRET, after)}, code
assert 1 <= int(seconds) <= 30
second = listed["Second"]["id"]
code = run("auth", "code", second).split()[0]
key = base64.b32encode(b"12345678901234567890123456789012").decode()
assert code in {totp(key, before, 8, digest=hashlib.sha256), totp(key, time.time(), 8, digest=hashlib.sha256)}
run("auth", "code", "0" * 32, status=1)
run("auth", "code", "../escape", status=1)

# Renaming and websites keep the account's record.
assert run("auth", "rename", fixture, "Fixture", "renamed@example.com") == "Saved\n"
assert run("auth", "sites", fixture, "https://GitHub.com/login", "account.proton.me") == "Saved\n"
listed = accounts()
assert listed["Fixture"]["id"] == fixture and listed["Fixture"]["account"] == "renamed@example.com"
assert listed["Fixture"]["sites"] == ["github.com", "account.proton.me"], listed["Fixture"]
run("auth", "sites", fixture, "github..com", status=1)
assert run("auth", "sites", fixture) == "Saved\n" and accounts()["Fixture"]["sites"] == []
assert run("auth", "import", stdin=FIXTURE) == "Added 0 accounts\n", "the same key was added twice"

# Aegis from a file; an encrypted export is refused.
export = output / "aegis.json"
export.write_text(AEGIS)
assert run("auth", "import", str(export)) == "Added 0 accounts\n"
assert run("auth", "remove", fixture) == "Removed\n"
assert run("auth", "import", str(export)) == "Added 1 account\n"
third = accounts()["Third"]
assert third["digits"] == 7 and third["period"] == 60
export.write_text(AEGIS_ENCRYPTED)
run("auth", "import", str(export), status=1)
run("auth", "import", str(output / "missing.json"), status=1)

# A QR image of the export, where the system can read one.
try:
    import qrcode
except ImportError:
    qrcode = None
zbar = any(Path(folder, "libzbar.so.0").exists() for folder in ("/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib"))
if qrcode and zbar:
    assert run("auth", "remove", second) == "Removed\n"
    image = output / "export.png"
    qrcode.make(MIGRATION).save(image)
    # Example Co has Third's key.
    assert run("auth", "import", str(image)) == "Added 1 account, skipped 1\n"
    assert sorted(accounts()) == ["Second", "Third"]
    qr = "QR image"
else:
    qr = "no QR image (needs python3-qrcode and libzbar0)"
assert run("sync", "status").endswith("Auth accounts: 2\n")
print(f"Werkzeug auth command: import, list, code, rename, websites, removal and {qr} without a window")
