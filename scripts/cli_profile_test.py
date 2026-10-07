#!/usr/bin/env python3
"""Exercise saved CLI identities using disposable secrets and configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tempfile
import termios
import time

from lesspass_compat_test import lesspass_password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True)
    parser.add_argument("--clipboard", action="store_true")
    args = parser.parse_args()
    cli = str(Path(args.cli).resolve())
    with tempfile.TemporaryDirectory(prefix="pass-profiles-") as temporary:
        home = Path(temporary)
        env = os.environ.copy()
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "LESSPASS_MASTER_PASSWORD"):
            env.pop(key, None)
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / "config"))
        config_path = home / "config/pass/profiles.json"
        config_path.parent.mkdir(parents=True)
        profile = dict(site="example.com", login="alice", length=23, counter=9,
                       lowercase=True, uppercase=True, digits=True, symbols=False,
                       exclude="0O1Il")
        config = dict(profiles={"w": {key: value for key, value in profile.items() if key != "site"}})

        def save():
            config_path.write_text(json.dumps(config))

        def run(*arguments, password="test master", settings=None):
            return subprocess.run([cli, *arguments], input=password + "\n", text=True,
                                  capture_output=True, env=settings or env, timeout=10)

        def expect(result, expected):
            assert result.returncode == 0, result.stderr
            assert result.stdout.rstrip("\n") == expected, "generated password differs from reference"

        save()
        expected = lesspass_password(profile, "test master")
        if not args.clipboard:
            expect(run("w", "example.com"), expected)
            expect(run("--profile", "w", "example.com"), expected)
            expect(run("example.com", "-P", "w"), expected)
            override = dict(profile, length=17, counter=2, symbols=True, exclude="")
            expect(run("w", "example.com", "--length", "17", "--counter", "2", "--symbols", "--exclude", ""),
                   lesspass_password(override, "test master"))
            assert run("--profile", "missing", "example.com").returncode != 0
            assert run("--profile", "w", "example.com", "extra").returncode != 0
            assert run("--prompt", "example.com", "alice", "argument").returncode != 0
            config["profiles"]["unicode"] = dict(config["profiles"]["w"], login="λ-user🐰")
            save()
            expect(run("unicode", "example.com"), lesspass_password(dict(profile, login="λ-user🐰"), "test master"))
            print("ok   CLI saved profiles, Unicode and explicit option precedence")

        vault = home / "test-vault"
        encrypted = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-md", "sha512", "-a",
                                    "-pbkdf2", "-iter", "100000", "-salt", "-pass", "pass:test unlock"],
                                   input=b"test master\n", capture_output=True, check=True, env=env).stdout
        vault.write_bytes(encrypted)
        config["vault"] = "~/test-vault"
        save()
        before = hashlib.sha256(config_path.read_bytes() + vault.read_bytes()).digest()
        configured = dict(env, LESSPASS_MASTER_PASSWORD="must not override configured vault")
        if not args.clipboard:
            expect(run("w", "example.com", password="test unlock", settings=configured), expected)
            expect(run("--prompt", "w", "example.com"), expected)
            config["profiles"]["w"]["vault"] = str(vault)
            config["vault"] = str(home / "missing-vault")
            save()
            expect(run("w", "example.com", password="test unlock"), expected)
            failed = run("w", "example.com", password="wrong unlock")
            assert failed.returncode != 0 and not failed.stdout
            assert "cannot unlock vault" in failed.stderr
            config["vault"] = str(vault)
            config["profiles"]["w"].pop("vault")
            save()
            before = hashlib.sha256(config_path.read_bytes() + vault.read_bytes()).digest()
            expect(run("w", "example.com", password="test unlock"), expected)
            assert hashlib.sha256(config_path.read_bytes() + vault.read_bytes()).digest() == before
            # Legacy vaults accepted base64 with or without wrapped whitespace.
            for body in (encrypted.replace(b"\n", b""), encrypted.replace(b"\n", b" \t\r\n")):
                vault.write_bytes(body)
                expect(run("w", "example.com", password="test unlock"), expected)
            vault.write_bytes(encrypted)
            print("ok   CLI vault unlocking, precedence, failure and unchanged storage")

            # Verify the real terminal prompt, hidden typing and restoration.
            master_fd, child_fd = pty.openpty()
            original = termios.tcgetattr(child_fd)
            child = subprocess.Popen([cli, "--no-copy", "w", "example.com"],
                                     stdin=child_fd, stderr=child_fd, stdout=subprocess.PIPE, env=env)
            try:
                received = b""
                deadline = time.monotonic() + 5
                while b"Vault passphrase: " not in received:
                    assert time.monotonic() < deadline, "terminal prompt missing"
                    if select.select([master_fd], [], [], 0.1)[0]:
                        received += os.read(master_fd, 4096)
                assert not termios.tcgetattr(child_fd)[3] & termios.ECHO
                os.write(master_fd, b"test unlock\n")
                output, _ = child.communicate(timeout=5)
                assert child.returncode == 0 and output.decode().strip() == expected
                assert termios.tcgetattr(child_fd) == original
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
                os.close(master_fd)
                os.close(child_fd)
            print("ok   CLI hidden terminal prompt and terminal state restoration")

            for interrupt in ("keyboard", "signal"):
                master_fd, child_fd = pty.openpty()
                original = termios.tcgetattr(child_fd)
                child = subprocess.Popen([cli, "--no-copy", "w", "example.com"],
                                         stdin=child_fd, stderr=child_fd, stdout=subprocess.PIPE, env=env)
                try:
                    received = b""
                    deadline = time.monotonic() + 5
                    while b"Vault passphrase: " not in received:
                        assert time.monotonic() < deadline, "terminal prompt missing"
                        if select.select([master_fd], [], [], 0.1)[0]:
                            received += os.read(master_fd, 4096)
                    if interrupt == "keyboard":
                        os.write(master_fd, b"\x03")
                    else:
                        child.send_signal(signal.SIGTERM)
                    output, _ = child.communicate(timeout=3)
                    assert child.returncode != 0 and not output
                    assert termios.tcgetattr(child_fd) == original
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
                    os.close(master_fd)
                    os.close(child_fd)
            print("ok   CLI Ctrl-C and signal cancellation restore terminal settings")

            config_path.write_text('{"profiles":')
            failed = run("w", "example.com")
            assert failed.returncode != 0 and not failed.stdout
            print("ok   CLI rejects malformed configuration without generating a different password")
            return

        assert os.environ.get("PASS_TEST_PRIVATE_DISPLAY") == "1", "clipboard tests require the private Xvfb harness"
        clipboard_env = dict(env, DISPLAY=os.environ["DISPLAY"])
        if "XAUTHORITY" in os.environ:
            clipboard_env["XAUTHORITY"] = os.environ["XAUTHORITY"]
        config.update(copy=True, clear_after="1s")
        save()
        before = hashlib.sha256(config_path.read_bytes() + vault.read_bytes()).digest()

        def clipboard():
            result = subprocess.run(["xclip", "-selection", "clipboard", "-out"],
                                    env=clipboard_env, capture_output=True, text=True, timeout=3)
            return result.stdout

        copied = run("w", "example.com", password="test unlock", settings=clipboard_env)
        assert copied.returncode == 0 and not copied.stdout, copied.stderr
        assert "Password copied" in copied.stderr and clipboard() == expected
        time.sleep(1.3)
        assert clipboard() == "", "password selection did not expire"
        copied = run("w", "example.com", password="test unlock", settings=clipboard_env)
        assert copied.returncode == 0 and clipboard() == expected
        subprocess.run(["xclip", "-selection", "clipboard", "-in"], input=b"another application",
                       env=clipboard_env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        time.sleep(1.3)
        assert clipboard() == "another application", "expiration overwrote another clipboard owner"
        expect(run("w", "example.com", "--no-copy", password="test unlock", settings=clipboard_env), expected)
        assert clipboard() == "another application"
        assert hashlib.sha256(config_path.read_bytes() + vault.read_bytes()).digest() == before
        print("ok   CLI profile clipboard copy, expiration, replacement ownership and --no-copy on private Xvfb")


if __name__ == "__main__":
    main()
